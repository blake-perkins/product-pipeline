#!/usr/bin/env python3
"""Traceability Checker — core quality gate tool for the Product Pipeline.

Implements three quality gates:
  Gate A: Uncovered Verification Criteria — VCs with no matching @VC tag in any
          .feature file.  Auto-generates stub .feature files.
  Gate B: Verification-Criteria Drift — detects when VC criteria text
          changes (SHA-256 comparison against .traceability-baseline.json) and
          injects @REVIEW_REQUIRED into the affected feature files.
  Gate C: Orphaned Scenarios — Gherkin scenarios whose @REQ or @VC tag
          references a requirement or VC that no longer exists.

When a release plan is provided (``--release-plan``), Gate A distinguishes
between truly uncovered VCs (in-scope for the current release) and
**deferred** VCs (scheduled for a future release).  Deferred VCs are
reported but do not cause Gate A to fail.

Exit codes:
  0  all gates pass
  1  one or more gates failed (or --fail-on-* triggered)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import textwrap
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG = logging.getLogger("traceability_checker")
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(message)s",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REQ_TAG_PATTERN = re.compile(r"@REQ[:\-_](\S+)", re.IGNORECASE)
VC_TAG_PATTERN = re.compile(r"@VC[:\-_](\S+)", re.IGNORECASE)
SCENARIO_HEADER_RE = re.compile(
    r"^\s*(Scenario Outline|Scenario|Example):", re.IGNORECASE
)
TAG_LINE_RE = re.compile(r"^\s*@")
VERIFICATION_METHODS_NON_TEST = frozenset({"Analysis", "Demonstration", "Inspection"})

INLINE_STUB_TEMPLATE = textwrap.dedent(
    """\
    @REQ:{{ requirement.requirementId }} @VC:{{ vc.verificationId }}{% if vc.verificationMethod not in ["Test"] %} @manual{% endif %}

    Feature: {{ requirement.name }}
      {{ requirement.description | default("No description provided.", true) }}

      Scenario: Verify {{ requirement.name }} — {{ vc.verificationId }}
        # Auto-generated stub — implement or replace with real steps.
        # Verification method: {{ vc.verificationMethod }}
        # Verification criteria: {{ vc.verificationDescription }}
        Given the system is set up for requirement {{ requirement.requirementId }}
        When the verification procedure is executed
        Then the requirement "{{ requirement.name }}" is satisfied
    """
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class VerificationCriteria:
    """Single verification criteria attached to a requirement."""

    vc_id: str
    method: str  # Analysis | Demonstration | Inspection | Test
    criteria: str

    @property
    def criteria_hash(self) -> str:
        """SHA-256 hex digest of the criteria text."""
        return hashlib.sha256(self.criteria.encode("utf-8")).hexdigest()

    @property
    def is_non_test(self) -> bool:
        return self.method in VERIFICATION_METHODS_NON_TEST

    @classmethod
    def from_dict(cls, data: dict) -> "VerificationCriteria":
        return cls(
            vc_id=data.get("verificationId", data.get("verificationCriteriaId", data.get("verificationMethodId", ""))),
            method=data.get("verificationMethod", data.get("method", "Test")),
            criteria=data.get("verificationDescription", data.get("criteria", "")),
        )


@dataclass
class Requirement:
    """Single requirement parsed from requirements.json."""

    requirement_id: str
    cameo_uuid: str
    name: str
    description: str
    verification_criteria_list: list[VerificationCriteria]
    status: str
    parent_requirement_id: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Requirement:
        # Parse verificationCriteria array; fall back to verificationMethods (old name),
        # then to legacy flat fields
        raw_vcs = data.get("verificationCriteria", data.get("verificationMethods"))
        if raw_vcs and isinstance(raw_vcs, list):
            vcs = [VerificationCriteria.from_dict(vc) for vc in raw_vcs]
        else:
            # Legacy format: single verificationMethod / verificationCriteria
            vc_id = f"{data['requirementId']}-VC-01"
            vcs = [
                VerificationCriteria(
                    vc_id=vc_id,
                    method=data.get("verificationMethod", "Test"),
                    criteria=data.get("verificationCriteria", ""),
                )
            ]

        return cls(
            requirement_id=data["requirementId"],
            cameo_uuid=data.get("cameoUUID", ""),
            name=data.get("name", data.get("title", "")),
            description=data.get("description", ""),
            verification_criteria_list=vcs,
            status=data.get("status", ""),
            parent_requirement_id=data.get("parentRequirementId"),
        )

    @property
    def all_vc_ids(self) -> list[str]:
        return [vc.vc_id for vc in self.verification_criteria_list]

    def vc_by_id(self, vc_id: str) -> VerificationCriteria | None:
        return next((vc for vc in self.verification_criteria_list if vc.vc_id == vc_id), None)


@dataclass
class ScenarioRef:
    """A scenario found in a .feature file that carries @REQ / @VC tags."""

    feature_file: Path
    scenario_name: str
    line_number: int
    req_ids: list[str]
    vc_ids: list[str] = field(default_factory=list)


@dataclass
class GateResult:
    """Outcome of a single quality gate."""

    gate: str
    passed: bool
    items: list[dict[str, Any]] = field(default_factory=list)
    message: str = ""


@dataclass
class TraceabilityReport:
    """Full report emitted after all gates have run."""

    timestamp: str
    requirements_total: int
    features_scanned: int
    vcs_total: int
    vcs_covered: int
    gate_a: GateResult
    gate_b: GateResult
    gate_c: GateResult
    overall_pass: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Requirements loading
# ---------------------------------------------------------------------------
def load_requirements(path: Path) -> dict[str, Requirement]:
    """Load and index requirements by requirementId."""
    if not path.exists():
        LOG.error("Requirements file not found: %s", path)
        sys.exit(1)

    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    if isinstance(raw, dict):
        # Support both {"requirements": [...]} wrapper and bare list.
        raw = raw.get("requirements", [raw])

    requirements: dict[str, Requirement] = {}
    for entry in raw:
        try:
            req = Requirement.from_dict(entry)
        except KeyError as exc:
            LOG.warning(
                "Skipping requirement entry missing key %s: %s", exc, entry
            )
            continue
        if req.requirement_id in requirements:
            LOG.warning("Duplicate requirementId: %s", req.requirement_id)
        requirements[req.requirement_id] = req

    LOG.info("Loaded %d requirements from %s", len(requirements), path)
    return requirements


# ---------------------------------------------------------------------------
# Feature file scanning
# ---------------------------------------------------------------------------
def scan_features(features_dir: Path) -> tuple[list[ScenarioRef], set[str], set[str]]:
    """Walk *features_dir* for .feature files and extract @REQ / @VC tags.

    Returns (list_of_ScenarioRef, set_of_all_req_ids_found, set_of_all_vc_ids_found).
    """
    if not features_dir.is_dir():
        LOG.error("Features directory does not exist: %s", features_dir)
        sys.exit(1)

    scenario_refs: list[ScenarioRef] = []
    all_req_ids: set[str] = set()
    all_vc_ids: set[str] = set()

    feature_header_re = re.compile(r"^\s*Feature:", re.IGNORECASE)

    for feature_file in sorted(features_dir.rglob("*.feature")):
        lines = feature_file.read_text(encoding="utf-8").splitlines()
        pending_tags: list[str] = []
        pending_vc_tags: list[str] = []
        feature_tags: list[str] = []  # REQ tags on Feature line, inherited by all Scenarios
        feature_vc_tags: list[str] = []  # VC tags on Feature line, inherited

        for line_no, line in enumerate(lines, start=1):
            # Collect tags (may span multiple lines before a Feature or Scenario).
            if TAG_LINE_RE.match(line):
                pending_tags.extend(REQ_TAG_PATTERN.findall(line))
                pending_vc_tags.extend(VC_TAG_PATTERN.findall(line))
            elif feature_header_re.match(line):
                # Tags before Feature: are feature-level — inherit into all scenarios
                feature_tags = list(pending_tags)
                feature_vc_tags = list(pending_vc_tags)
                pending_tags = []
                pending_vc_tags = []
            elif SCENARIO_HEADER_RE.match(line):
                # Merge feature-level tags with any scenario-level tags
                merged_req = list(set(feature_tags + pending_tags))
                merged_vc = list(set(feature_vc_tags + pending_vc_tags))
                if merged_req or merged_vc:
                    scenario_name = line.strip().split(":", 1)[-1].strip()
                    ref = ScenarioRef(
                        feature_file=feature_file,
                        scenario_name=scenario_name,
                        line_number=line_no,
                        req_ids=merged_req,
                        vc_ids=merged_vc,
                    )
                    scenario_refs.append(ref)
                    all_req_ids.update(merged_req)
                    all_vc_ids.update(merged_vc)
                pending_tags = []
                pending_vc_tags = []
            else:
                # Non-tag, non-scenario line — reset pending tags only if it is
                # not blank (blank lines between tag rows are acceptable).
                if line.strip():
                    pending_tags = []
                    pending_vc_tags = []

    LOG.info(
        "Scanned %d .feature files, found %d scenario(s) referencing %d unique requirement(s) and %d unique VC(s)",
        sum(1 for _ in features_dir.rglob("*.feature")),
        len(scenario_refs),
        len(all_req_ids),
        len(all_vc_ids),
    )
    return scenario_refs, all_req_ids, all_vc_ids


# ---------------------------------------------------------------------------
# Stub generation (Gate A helper)
# ---------------------------------------------------------------------------
def _render_stub(requirement: Requirement, vc: VerificationCriteria, template_path: Path | None, deferred: bool = False) -> str:
    """Render a stub .feature file for an uncovered VC.

    Tries Jinja2 template at *template_path* first; falls back to the inline
    template.
    """
    context = {
        "requirement": {
            "requirementId": requirement.requirement_id,
            "name": requirement.name,
            "description": requirement.description,
        },
        "vc": {
            "verificationId": vc.vc_id,
            "verificationMethod": vc.method,
            "verificationDescription": vc.criteria,
            "deferred": deferred,
        },
    }

    if template_path and template_path.is_file():
        try:
            from jinja2 import Environment, FileSystemLoader

            env = Environment(
                loader=FileSystemLoader(str(template_path.parent)),
                keep_trailing_newline=True,
            )
            tmpl = env.get_template(template_path.name)
            return tmpl.render(**context)
        except ImportError:
            LOG.warning(
                "Jinja2 not installed; falling back to inline template."
            )
        except Exception as exc:  # noqa: BLE001
            LOG.warning(
                "Failed to render Jinja2 template %s: %s — falling back to inline template.",
                template_path,
                exc,
            )

    # Inline fallback (manual mini-template rendering).
    req = context["requirement"]
    vc_ctx = context["vc"]
    is_test = vc_ctx["verificationMethod"] == "Test"
    tag_line = f"@REQ:{req['requirementId']} @VC:{vc_ctx['verificationId']}"
    if vc_ctx.get("deferred"):
        tag_line += " @DEFERRED"
    if not is_test:
        tag_line += " @manual"

    description = req["description"] or "No description provided."
    criteria = vc_ctx["verificationDescription"] or "N/A"

    return (
        f"{tag_line}\n"
        f"\n"
        f"Feature: {req['name']}\n"
        f"  {description}\n"
        f"\n"
        f"  Scenario: Verify {req['name']} — {vc_ctx['verificationId']}\n"
        f"    # Auto-generated stub — implement or replace with real steps.\n"
        f"    # Verification method: {vc_ctx['verificationMethod']}\n"
        f"    # Verification criteria: {criteria}\n"
        f"    Given the system is set up for requirement {req['requirementId']}\n"
        f"    When the verification procedure is executed\n"
        f"    Then the requirement \"{req['name']}\" is satisfied\n"
    )


def generate_stubs(
    uncovered_vcs: list[tuple[Requirement, VerificationCriteria]],
    stubs_output_dir: Path,
    non_test_output_dir: Path | None,
    template_path: Path | None,
    deferred: bool = False,
) -> list[Path]:
    """Create stub .feature files for every uncovered VC.

    Non-Test VCs are placed in *non_test_output_dir* (if given) with
    an additional ``@manual`` tag.  When *deferred* is True, stubs
    include the ``@DEFERRED`` tag.
    """
    created: list[Path] = []

    for req, vc in uncovered_vcs:
        if vc.is_non_test and non_test_output_dir is not None:
            out_dir = non_test_output_dir
        else:
            out_dir = stubs_output_dir

        out_dir.mkdir(parents=True, exist_ok=True)

        safe_id = re.sub(r"[^\w\-.]", "_", vc.vc_id)
        stub_path = out_dir / f"{safe_id}.feature"

        content = _render_stub(req, vc, template_path, deferred=deferred)
        stub_path.write_text(content, encoding="utf-8")
        LOG.info("Generated stub: %s", stub_path)
        created.append(stub_path)

    return created


# ---------------------------------------------------------------------------
# Baseline management (Gate B helper)
# ---------------------------------------------------------------------------
def load_baseline(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Load the traceability baseline file.

    Parameters
    ----------
    path:
        Path to ``.traceability-baseline.json``.

    Returns
    -------
    tuple[dict[str, str], dict[str, str]]
        A ``(hashes, criteria)`` pair of dicts, each keyed by VC ID.
        *hashes* maps VC IDs to their SHA-256 digest of the verification
        criteria text; *criteria* maps VC IDs to the raw criteria string.
        Returns empty dicts if the file does not exist.
    """
    if not path.exists():
        return {}, {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("hashes", {}), data.get("criteria", {})


def load_release_plan(
    path: Path | None,
    requirements: dict[str, Requirement],
    current_version: str | None = None,
) -> tuple[set[str], dict[str, str], list[dict[str, Any]]]:
    """Load release plan and resolve in-scope VC IDs for the current version.

    Returns
    -------
    tuple
        ``(in_scope_vc_ids, vc_to_release, releases)`` where
        ``in_scope_vc_ids`` is the cumulative set of VC IDs in scope for
        the current version and all prior releases, ``vc_to_release`` maps
        every VC ID to its first-planned release version, and ``releases``
        is the raw release list for dashboard rendering.
    """
    if path is None or not path.is_file():
        # No release plan — all VCs are in scope
        all_vcs: set[str] = set()
        for req in requirements.values():
            all_vcs.update(req.all_vc_ids)
        return all_vcs, {}, []

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    releases = data.get("releases", [])
    if not releases:
        all_vcs = set()
        for req in requirements.values():
            all_vcs.update(req.all_vc_ids)
        return all_vcs, {}, releases

    # Build vc_to_release: first release a VC appears in
    vc_to_release: dict[str, str] = {}
    for rel in releases:
        version = rel.get("version", "")
        for scope_id in rel.get("scope", []):
            # Check if it's a VC ID or a requirement ID
            if _is_vc_id_pattern(scope_id):
                vc_to_release.setdefault(scope_id, version)
            else:
                # Requirement ID — expand to all its VCs
                req = requirements.get(scope_id)
                if req:
                    for vc in req.verification_criteria_list:
                        vc_to_release.setdefault(vc.vc_id, version)

    # Compute cumulative in-scope VCs (current release + all prior)
    in_scope: set[str] = set()
    if current_version:
        found_current = False
        for rel in releases:
            for scope_id in rel.get("scope", []):
                if _is_vc_id_pattern(scope_id):
                    in_scope.add(scope_id)
                else:
                    req = requirements.get(scope_id)
                    if req:
                        for vc in req.verification_criteria_list:
                            in_scope.add(vc.vc_id)
            if rel.get("version") == current_version:
                found_current = True
                break
        if not found_current:
            LOG.warning(
                "Release version '%s' not found in release plan. "
                "All VCs treated as in-scope.",
                current_version,
            )
            for req in requirements.values():
                in_scope.update(req.all_vc_ids)
    else:
        # No version specified — all VCs in scope
        for req in requirements.values():
            in_scope.update(req.all_vc_ids)

    LOG.info(
        "Release plan loaded: %d releases, %d VCs in scope for %s",
        len(releases),
        len(in_scope),
        current_version or "(all)",
    )
    return in_scope, vc_to_release, releases


def _is_vc_id_pattern(s: str) -> bool:
    """Check if string looks like a VC ID (has -VC- suffix)."""
    return bool(re.match(r"^[A-Z]+-[A-Z]+-\d{3,}-VC-\d{2,}$", s))


def load_current_version(version_file: Path | None, cli_override: str | None) -> str | None:
    """Resolve the current release version from CLI override or VERSION file."""
    if cli_override:
        return cli_override
    if version_file and version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip()
    return None


def save_baseline(
    path: Path, requirements: dict[str, Requirement]
) -> None:
    """Persist current VC criteria hashes and text to baseline."""
    hashes: dict[str, str] = {}
    criteria: dict[str, str] = {}
    for req in requirements.values():
        for vc in req.verification_criteria_list:
            hashes[vc.vc_id] = vc.criteria_hash
            criteria[vc.vc_id] = vc.criteria
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hashes": hashes,
        "criteria": criteria,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    LOG.info("Baseline written to %s (%d entries)", path, len(hashes))


def detect_drift(
    requirements: dict[str, Requirement],
    baseline: dict[str, str],
    baseline_criteria: dict[str, str] | None = None,
) -> list[tuple[Requirement, VerificationCriteria, str | None]]:
    """Return (requirement, vc, old_criteria) tuples whose criteria hash differs from baseline."""
    baseline_criteria = baseline_criteria or {}
    drifted: list[tuple[Requirement, VerificationCriteria, str | None]] = []
    for req in requirements.values():
        for vc in req.verification_criteria_list:
            old_hash = baseline.get(vc.vc_id)
            if old_hash is not None and old_hash != vc.criteria_hash:
                old_text = baseline_criteria.get(vc.vc_id)
                drifted.append((req, vc, old_text))
    return drifted


def inject_review_tag(feature_file: Path, vc_id: str) -> bool:
    """Add @REVIEW_REQUIRED tag to scenarios in *feature_file* tagged with *vc_id*.

    Returns True if any modification was made.
    """
    text = feature_file.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    modified = False

    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for a tag line that references the drifted VC.
        if TAG_LINE_RE.match(line) and re.search(
            rf"@VC[:\-_]{re.escape(vc_id)}\b", line
        ):
            # Check if @REVIEW_REQUIRED is already present on this or adjacent
            # tag lines.
            block_start = i
            block_end = i
            while block_end + 1 < len(lines) and TAG_LINE_RE.match(
                lines[block_end + 1]
            ):
                block_end += 1

            block_text = "".join(lines[block_start : block_end + 1])
            if "@REVIEW_REQUIRED" not in block_text:
                # Insert @REVIEW_REQUIRED on the tag line itself.
                lines[i] = line.rstrip("\n") + " @REVIEW_REQUIRED\n"
                modified = True

            i = block_end + 1
        else:
            i += 1

    if modified:
        feature_file.write_text("".join(lines), encoding="utf-8")
        LOG.info(
            "Injected @REVIEW_REQUIRED into %s for VC %s",
            feature_file,
            vc_id,
        )

    return modified


# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------
def run_gate_a(
    requirements: dict[str, Requirement],
    covered_vc_ids: set[str],
    stubs_output_dir: Path,
    non_test_output_dir: Path | None,
    template_path: Path | None,
    fail_on_uncovered: bool,
    in_scope_vc_ids: set[str] | None = None,
    vc_to_release: dict[str, str] | None = None,
) -> GateResult:
    """Gate A -- Uncovered Verification Criteria.

    Identifies VCs that have no matching ``@VC:`` tag in any ``.feature``
    file and auto-generates stub features for them.

    Parameters
    ----------
    requirements:
        Mapping of requirement ID to :class:`Requirement` objects.
    covered_vc_ids:
        Set of VC IDs already covered by existing Gherkin scenarios.
    stubs_output_dir:
        Directory where generated stub ``.feature`` files are written.
    non_test_output_dir:
        Optional directory for non-test verification criteria stubs.
    template_path:
        Optional Jinja2 template for stub generation.
    fail_on_uncovered:
        If *True*, the gate fails when any in-scope VC is uncovered.
    in_scope_vc_ids:
        When provided (derived from a release plan), only VCs in this set
        are considered in-scope for the current release.  VCs outside
        this set are marked as **deferred** rather than uncovered, and
        do not cause the gate to fail.
    vc_to_release:
        Mapping of deferred VC IDs to their target release labels,
        used to annotate deferred items in the gate report.

    Returns
    -------
    GateResult
        Outcome of the gate, including itemised uncovered and deferred VCs.
    """
    vc_to_release = vc_to_release or {}

    uncovered_vcs: list[tuple[Requirement, VerificationCriteria]] = []
    deferred_vcs: list[tuple[Requirement, VerificationCriteria]] = []

    for _rid, req in sorted(requirements.items()):
        for vc in req.verification_criteria_list:
            if vc.vc_id not in covered_vc_ids:
                if in_scope_vc_ids is not None and vc.vc_id not in in_scope_vc_ids:
                    deferred_vcs.append((req, vc))
                else:
                    uncovered_vcs.append((req, vc))

    if not uncovered_vcs and not deferred_vcs:
        return GateResult(
            gate="A",
            passed=True,
            message="All verification criteria are covered by at least one scenario.",
        )

    # Generate stubs for uncovered VCs
    stubs = generate_stubs(
        uncovered_vcs, stubs_output_dir, non_test_output_dir, template_path
    ) if uncovered_vcs else []

    # Generate stubs for deferred VCs (with @DEFERRED tag)
    deferred_stubs = generate_stubs(
        deferred_vcs, stubs_output_dir, non_test_output_dir, template_path,
        deferred=True,
    ) if deferred_vcs else []

    items = [
        {
            "requirementId": req.requirement_id,
            "verificationId": vc.vc_id,
            "verificationMethod": vc.method,
            "name": req.name,
            "stubGenerated": str(stub),
            "deferred": False,
        }
        for (req, vc), stub in zip(uncovered_vcs, stubs)
    ]

    # Add deferred items (not counted toward failure)
    for i, (req, vc) in enumerate(deferred_vcs):
        item = {
            "requirementId": req.requirement_id,
            "verificationId": vc.vc_id,
            "verificationMethod": vc.method,
            "name": req.name,
            "deferred": True,
            "targetRelease": vc_to_release.get(vc.vc_id, ""),
        }
        if deferred_stubs and i < len(deferred_stubs):
            item["stubGenerated"] = str(deferred_stubs[i])
        items.append(item)

    # Only truly uncovered VCs (in-scope) count toward failure
    passed = not fail_on_uncovered or len(uncovered_vcs) == 0

    parts = []
    if uncovered_vcs:
        parts.append(f"{len(uncovered_vcs)} uncovered (in-scope)")
    if deferred_vcs:
        parts.append(f"{len(deferred_vcs)} deferred to future releases")
    if stubs:
        parts.append(f"{len(stubs)} stub(s) generated")
    if not uncovered_vcs and deferred_vcs:
        parts.insert(0, "All in-scope verification criteria covered")

    msg = "; ".join(parts) + "."
    if uncovered_vcs:
        LOG.warning("Gate A: %s", msg)
    else:
        LOG.info("Gate A: %s", msg)

    return GateResult(gate="A", passed=passed, items=items, message=msg)


def run_gate_b(
    requirements: dict[str, Requirement],
    scenario_refs: list[ScenarioRef],
    baseline: dict[str, str],
    baseline_criteria: dict[str, str] | None = None,
) -> GateResult:
    """Gate B — Verification Criteria Drift."""
    if not baseline:
        return GateResult(
            gate="B",
            passed=True,
            message="No baseline found; skipping drift detection. Run with --update-baseline to create one.",
        )

    baseline_criteria = baseline_criteria or {}
    drifted = detect_drift(requirements, baseline, baseline_criteria)

    if not drifted:
        return GateResult(
            gate="B",
            passed=True,
            message="No verification-criteria drift detected.",
        )

    # Build a lookup: vc_id -> list of feature files.
    vc_to_files: dict[str, set[Path]] = {}
    for ref in scenario_refs:
        for vid in ref.vc_ids:
            vc_to_files.setdefault(vid, set()).add(ref.feature_file)

    items: list[dict[str, Any]] = []
    files_modified: set[Path] = set()
    for req, vc, old_criteria_text in drifted:
        affected_files = vc_to_files.get(vc.vc_id, set())
        for ff in affected_files:
            if inject_review_tag(ff, vc.vc_id):
                files_modified.add(ff)

        items.append(
            {
                "requirementId": req.requirement_id,
                "verificationId": vc.vc_id,
                "name": req.name,
                "oldHash": baseline.get(vc.vc_id, ""),
                "newHash": vc.criteria_hash,
                "oldCriteria": old_criteria_text,
                "newCriteria": vc.criteria,
                "affectedFeatureFiles": [str(f) for f in sorted(affected_files)],
            }
        )

    msg = (
        f"{len(drifted)} verification criteria with drifted criteria; "
        f"@REVIEW_REQUIRED injected into {len(files_modified)} file(s)."
    )
    LOG.warning("Gate B: %s", msg)

    # Drift causes pipeline failure — forces human review of changed criteria.
    # Developer must update scenarios, remove @REVIEW_REQUIRED, and run --update-baseline.
    return GateResult(gate="B", passed=False, items=items, message=msg)


def run_gate_c(
    requirements: dict[str, Requirement],
    scenario_refs: list[ScenarioRef],
    all_valid_vc_ids: set[str],
    fail_on_orphaned: bool,
) -> GateResult:
    """Gate C — Orphaned Scenarios."""
    orphans: list[dict[str, Any]] = []
    for ref in scenario_refs:
        missing_reqs = [rid for rid in ref.req_ids if rid not in requirements]
        missing_vcs = [vid for vid in ref.vc_ids if vid not in all_valid_vc_ids]
        if missing_reqs or missing_vcs:
            orphan_entry: dict[str, Any] = {
                "featureFile": str(ref.feature_file),
                "scenarioName": ref.scenario_name,
                "lineNumber": ref.line_number,
            }
            if missing_reqs:
                orphan_entry["orphanedReqIds"] = missing_reqs
            if missing_vcs:
                orphan_entry["orphanedVcIds"] = missing_vcs
            orphans.append(orphan_entry)

    if not orphans:
        return GateResult(
            gate="C",
            passed=True,
            message="No orphaned scenarios detected.",
        )

    passed = not fail_on_orphaned
    msg = (
        f"{len(orphans)} scenario(s) reference requirement(s) or VC(s) that no longer exist."
    )
    LOG.warning("Gate C: %s", msg)

    return GateResult(gate="C", passed=passed, items=orphans, message=msg)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def build_report(
    requirements: dict[str, Requirement],
    features_dir: Path,
    covered_vc_ids: set[str],
    gate_a: GateResult,
    gate_b: GateResult,
    gate_c: GateResult,
) -> TraceabilityReport:
    feature_count = sum(1 for _ in features_dir.rglob("*.feature"))
    overall = gate_a.passed and gate_b.passed and gate_c.passed

    # Count total VCs across all requirements
    vcs_total = sum(len(req.verification_criteria_list) for req in requirements.values())
    # Collect all valid VC IDs
    all_valid_vc_ids: set[str] = set()
    for req in requirements.values():
        all_valid_vc_ids.update(req.all_vc_ids)
    vcs_covered = len(covered_vc_ids & all_valid_vc_ids)

    return TraceabilityReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        requirements_total=len(requirements),
        features_scanned=feature_count,
        vcs_total=vcs_total,
        vcs_covered=vcs_covered,
        gate_a=gate_a,
        gate_b=gate_b,
        gate_c=gate_c,
        overall_pass=overall,
    )


def write_json_report(report: TraceabilityReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report.to_dict(), fh, indent=2)
    LOG.info("JSON report written to %s", path)


def write_html_report(report: TraceabilityReport, path: Path) -> None:
    """Generate a self-contained HTML traceability report."""

    def _gate_row(gate: GateResult) -> str:
        status = "PASS" if gate.passed else "FAIL"
        color = "#2e7d32" if gate.passed else "#c62828"
        count = len(gate.items)
        return (
            f"<tr>"
            f'<td>Gate {gate.gate}</td>'
            f'<td style="color:{color};font-weight:bold">{status}</td>'
            f"<td>{count}</td>"
            f"<td>{gate.message}</td>"
            f"</tr>"
        )

    def _detail_section(gate: GateResult) -> str:
        if not gate.items:
            return ""
        rows = "".join(
            f"<tr>{''.join(f'<td>{v}</td>' for v in item.values())}</tr>"
            for item in gate.items
        )
        headers = "".join(
            f"<th>{k}</th>" for k in gate.items[0].keys()
        )
        return (
            f"<h3>Gate {gate.gate} Details</h3>"
            f"<table><thead><tr>{headers}</tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )

    html = textwrap.dedent(
        f"""\
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <title>Traceability Report</title>
          <style>
            body {{ font-family: sans-serif; margin: 2rem; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }}
            th, td {{ border: 1px solid #ccc; padding: .5rem .75rem; text-align: left; }}
            th {{ background: #f5f5f5; }}
            h1 {{ margin-bottom: .25rem; }}
            .meta {{ color: #666; margin-bottom: 1.5rem; }}
          </style>
        </head>
        <body>
          <h1>Traceability Report</h1>
          <p class="meta">
            Generated: {report.timestamp}<br>
            Requirements: {report.requirements_total} |
            Feature files scanned: {report.features_scanned} |
            VCs total: {report.vcs_total} |
            VCs covered: {report.vcs_covered} |
            Overall: <strong style="color:{'#2e7d32' if report.overall_pass else '#c62828'}">
              {'PASS' if report.overall_pass else 'FAIL'}</strong>
          </p>
          <h2>Summary</h2>
          <table>
            <thead><tr><th>Gate</th><th>Status</th><th>Items</th><th>Message</th></tr></thead>
            <tbody>
              {_gate_row(report.gate_a)}
              {_gate_row(report.gate_b)}
              {_gate_row(report.gate_c)}
            </tbody>
          </table>
          {_detail_section(report.gate_a)}
          {_detail_section(report.gate_b)}
          {_detail_section(report.gate_c)}
        </body>
        </html>
        """
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    LOG.info("HTML report written to %s", path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Traceability Checker — quality gates for the Product Pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    p.add_argument(
        "--requirements",
        type=Path,
        required=True,
        help="Path to requirements.json (from Cameo export).",
    )
    p.add_argument(
        "--features-dir",
        type=Path,
        required=True,
        help="Root directory containing .feature files.",
    )
    p.add_argument(
        "--stubs-output-dir",
        type=Path,
        required=True,
        help="Directory for generated stub .feature files.",
    )
    p.add_argument(
        "--non-test-output-dir",
        type=Path,
        default=None,
        help="Directory for non-Test verification criteria stubs (default: stubs-output-dir/non_test).",
    )
    p.add_argument(
        "--report-output",
        type=Path,
        required=True,
        help="Path for the JSON traceability report.",
    )
    p.add_argument(
        "--html-report-output",
        type=Path,
        default=None,
        help="Optional path for an HTML traceability report.",
    )
    p.add_argument(
        "--baseline-path",
        type=Path,
        default=None,
        help="Path to .traceability-baseline.json (default: <features-dir>/.traceability-baseline.json).",
    )
    p.add_argument(
        "--update-baseline",
        action="store_true",
        help="Update baseline without running gates, then exit.",
    )
    p.add_argument(
        "--fail-on-uncovered",
        action="store_true",
        help="Exit with code 1 if uncovered verification criteria are found.",
    )
    p.add_argument(
        "--fail-on-orphaned",
        action="store_true",
        help="Exit with code 1 if orphaned scenarios are found.",
    )
    p.add_argument(
        "--release-plan",
        type=Path,
        default=None,
        help="Path to release-plan.json (maps requirements/VCs to release versions).",
    )
    p.add_argument(
        "--release",
        type=str,
        default=None,
        help="Override the current release version (default: read from VERSION file).",
    )

    args = p.parse_args(argv)

    if args.baseline_path is None:
        args.baseline_path = args.features_dir / ".traceability-baseline.json"

    if args.non_test_output_dir is None:
        args.non_test_output_dir = args.stubs_output_dir / "non_test"

    return args


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # --- Load requirements ---------------------------------------------------
    requirements = load_requirements(args.requirements)

    if not requirements:
        LOG.error("No valid requirements found in %s", args.requirements)
        return 1

    # --- Baseline-only mode ---------------------------------------------------
    if args.update_baseline:
        save_baseline(args.baseline_path, requirements)
        LOG.info("Baseline updated. Exiting without running gates.")
        return 0

    # --- Scan features --------------------------------------------------------
    scenario_refs, covered_req_ids, covered_vc_ids = scan_features(args.features_dir)

    # --- Build set of all valid VC IDs from requirements ----------------------
    all_valid_vc_ids: set[str] = set()
    for req in requirements.values():
        all_valid_vc_ids.update(req.all_vc_ids)

    # --- Load baseline --------------------------------------------------------
    baseline, baseline_criteria = load_baseline(args.baseline_path)

    # --- Load release plan ----------------------------------------------------
    release_plan_path = args.release_plan
    if release_plan_path is None:
        # Try default location in repo root
        default_plan = Path(args.requirements).resolve().parent.parent.parent / "release-plan.json"
        if default_plan.is_file():
            release_plan_path = default_plan

    version_file = Path(args.requirements).resolve().parent.parent.parent / "VERSION"
    current_version = load_current_version(
        version_file if version_file.is_file() else None,
        args.release,
    )

    in_scope_vc_ids, vc_to_release, releases = load_release_plan(
        release_plan_path, requirements, current_version
    )

    # --- Resolve Jinja2 template path -----------------------------------------
    template_path = Path(__file__).resolve().parent / "templates" / "stub_scenario.feature.j2"

    # --- Run gates ------------------------------------------------------------
    gate_a = run_gate_a(
        requirements=requirements,
        covered_vc_ids=covered_vc_ids,
        stubs_output_dir=args.stubs_output_dir,
        non_test_output_dir=args.non_test_output_dir,
        template_path=template_path,
        fail_on_uncovered=args.fail_on_uncovered,
        in_scope_vc_ids=in_scope_vc_ids,
        vc_to_release=vc_to_release,
    )

    gate_b = run_gate_b(
        requirements=requirements,
        scenario_refs=scenario_refs,
        baseline=baseline,
        baseline_criteria=baseline_criteria,
    )

    gate_c = run_gate_c(
        requirements=requirements,
        scenario_refs=scenario_refs,
        all_valid_vc_ids=all_valid_vc_ids,
        fail_on_orphaned=args.fail_on_orphaned,
    )

    # --- Update baseline after drift check ------------------------------------
    save_baseline(args.baseline_path, requirements)

    # --- Build and write reports ----------------------------------------------
    report = build_report(requirements, args.features_dir, covered_vc_ids, gate_a, gate_b, gate_c)

    write_json_report(report, args.report_output)

    if args.html_report_output:
        write_html_report(report, args.html_report_output)

    # --- Summary --------------------------------------------------------------
    LOG.info("=" * 60)
    LOG.info("Gate A (Uncovered):  %s — %s", "PASS" if gate_a.passed else "FAIL", gate_a.message)
    LOG.info("Gate B (Drift):      %s — %s", "PASS" if gate_b.passed else "FAIL", gate_b.message)
    LOG.info("Gate C (Orphaned):   %s — %s", "PASS" if gate_c.passed else "FAIL", gate_c.message)
    LOG.info("Overall:             %s", "PASS" if report.overall_pass else "FAIL")
    LOG.info("=" * 60)

    return 0 if report.overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())

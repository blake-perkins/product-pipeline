#!/usr/bin/env python3
"""Traceability Checker — core quality gate tool for the Product Pipeline.

Implements three quality gates:
  Gate A: Uncovered Requirements — requirements with no matching @REQ tag in any
          .feature file.  Auto-generates stub .feature files.
  Gate B: Verification-Criteria Drift — detects when verificationCriteria text
          changes (SHA-256 comparison against .traceability-baseline.json) and
          injects @REVIEW_REQUIRED into the affected feature files.
  Gate C: Orphaned Scenarios — Gherkin scenarios whose @REQ tag references a
          requirement that no longer exists.

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
SCENARIO_HEADER_RE = re.compile(
    r"^\s*(Scenario Outline|Scenario|Example):", re.IGNORECASE
)
TAG_LINE_RE = re.compile(r"^\s*@")
VERIFICATION_METHODS_NON_TEST = frozenset({"Analysis", "Demonstration", "Inspection"})

INLINE_STUB_TEMPLATE = textwrap.dedent(
    """\
    @REQ:{{ requirement.requirementId }}{% if requirement.verification_method not in ["Test"] %} @manual{% endif %}

    Feature: {{ requirement.title }}
      {{ requirement.description | default("No description provided.", true) }}

      Scenario: Verify {{ requirement.title }}
        # Auto-generated stub — implement or replace with real steps.
        # Verification method: {{ requirement.verification_method }}
        # Verification criteria: {{ requirement.verification_criteria }}
        Given the system is set up for requirement {{ requirement.requirementId }}
        When the verification procedure is executed
        Then the requirement "{{ requirement.title }}" is satisfied
    """
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class Requirement:
    """Single requirement parsed from requirements.json."""

    requirement_id: str
    cameo_uuid: str
    title: str
    description: str
    verification_method: str  # Analysis | Demonstration | Inspection | Test
    verification_criteria: str
    priority: str
    status: str
    parent_requirement_id: str | None
    satisfied_by: list[str] = field(default_factory=list)
    traces_to: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Requirement:
        return cls(
            requirement_id=data["requirementId"],
            cameo_uuid=data.get("cameoUUID", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            verification_method=data.get("verificationMethod", "Test"),
            verification_criteria=data.get("verificationCriteria", ""),
            priority=data.get("priority", ""),
            status=data.get("status", ""),
            parent_requirement_id=data.get("parentRequirementId"),
            satisfied_by=data.get("satisfiedBy", []),
            traces_to=data.get("tracesTo", []),
        )

    @property
    def criteria_hash(self) -> str:
        """SHA-256 hex digest of the verificationCriteria text."""
        return hashlib.sha256(
            self.verification_criteria.encode("utf-8")
        ).hexdigest()

    @property
    def is_non_test(self) -> bool:
        return self.verification_method in VERIFICATION_METHODS_NON_TEST


@dataclass
class ScenarioRef:
    """A scenario found in a .feature file that carries a @REQ tag."""

    feature_file: Path
    scenario_name: str
    line_number: int
    req_ids: list[str]


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
def scan_features(features_dir: Path) -> tuple[list[ScenarioRef], set[str]]:
    """Walk *features_dir* for .feature files and extract @REQ tags.

    Returns (list_of_ScenarioRef, set_of_all_req_ids_found).
    """
    if not features_dir.is_dir():
        LOG.error("Features directory does not exist: %s", features_dir)
        sys.exit(1)

    scenario_refs: list[ScenarioRef] = []
    all_req_ids: set[str] = set()

    feature_header_re = re.compile(r"^\s*Feature:", re.IGNORECASE)

    for feature_file in sorted(features_dir.rglob("*.feature")):
        lines = feature_file.read_text(encoding="utf-8").splitlines()
        pending_tags: list[str] = []
        feature_tags: list[str] = []  # Tags on Feature line, inherited by all Scenarios

        for line_no, line in enumerate(lines, start=1):
            # Collect tags (may span multiple lines before a Feature or Scenario).
            if TAG_LINE_RE.match(line):
                pending_tags.extend(REQ_TAG_PATTERN.findall(line))
            elif feature_header_re.match(line):
                # Tags before Feature: are feature-level — inherit into all scenarios
                feature_tags = list(pending_tags)
                pending_tags = []
            elif SCENARIO_HEADER_RE.match(line):
                # Merge feature-level tags with any scenario-level tags
                merged = list(set(feature_tags + pending_tags))
                if merged:
                    scenario_name = line.strip().split(":", 1)[-1].strip()
                    ref = ScenarioRef(
                        feature_file=feature_file,
                        scenario_name=scenario_name,
                        line_number=line_no,
                        req_ids=merged,
                    )
                    scenario_refs.append(ref)
                    all_req_ids.update(merged)
                pending_tags = []
            else:
                # Non-tag, non-scenario line — reset pending tags only if it is
                # not blank (blank lines between tag rows are acceptable).
                if line.strip():
                    pending_tags = []

    LOG.info(
        "Scanned %d .feature files, found %d scenario(s) referencing %d unique requirement(s)",
        sum(1 for _ in features_dir.rglob("*.feature")),
        len(scenario_refs),
        len(all_req_ids),
    )
    return scenario_refs, all_req_ids


# ---------------------------------------------------------------------------
# Stub generation (Gate A helper)
# ---------------------------------------------------------------------------
def _render_stub(requirement: Requirement, template_path: Path | None) -> str:
    """Render a stub .feature file for an uncovered requirement.

    Tries Jinja2 template at *template_path* first; falls back to the inline
    template.
    """
    context = {
        "requirement": {
            "requirementId": requirement.requirement_id,
            "title": requirement.title,
            "description": requirement.description,
            "verification_method": requirement.verification_method,
            "verification_criteria": requirement.verification_criteria,
        }
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
    is_test = req["verification_method"] == "Test"
    tag_line = f"@REQ:{req['requirementId']}"
    if not is_test:
        tag_line += " @manual"

    description = req["description"] or "No description provided."
    criteria = req["verification_criteria"] or "N/A"

    return (
        f"{tag_line}\n"
        f"\n"
        f"Feature: {req['title']}\n"
        f"  {description}\n"
        f"\n"
        f"  Scenario: Verify {req['title']}\n"
        f"    # Auto-generated stub — implement or replace with real steps.\n"
        f"    # Verification method: {req['verification_method']}\n"
        f"    # Verification criteria: {criteria}\n"
        f"    Given the system is set up for requirement {req['requirementId']}\n"
        f"    When the verification procedure is executed\n"
        f"    Then the requirement \"{req['title']}\" is satisfied\n"
    )


def generate_stubs(
    uncovered: list[Requirement],
    stubs_output_dir: Path,
    non_test_output_dir: Path | None,
    template_path: Path | None,
) -> list[Path]:
    """Create stub .feature files for every uncovered requirement.

    Non-Test requirements are placed in *non_test_output_dir* (if given) with
    an additional ``@manual`` tag.
    """
    created: list[Path] = []

    for req in uncovered:
        if req.is_non_test and non_test_output_dir is not None:
            out_dir = non_test_output_dir
        else:
            out_dir = stubs_output_dir

        out_dir.mkdir(parents=True, exist_ok=True)

        safe_id = re.sub(r"[^\w\-.]", "_", req.requirement_id)
        stub_path = out_dir / f"{safe_id}.feature"

        content = _render_stub(req, template_path)
        stub_path.write_text(content, encoding="utf-8")
        LOG.info("Generated stub: %s", stub_path)
        created.append(stub_path)

    return created


# ---------------------------------------------------------------------------
# Baseline management (Gate B helper)
# ---------------------------------------------------------------------------
def load_baseline(path: Path) -> dict[str, str]:
    """Load .traceability-baseline.json → {requirementId: sha256_hex}."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("hashes", {})


def save_baseline(
    path: Path, requirements: dict[str, Requirement]
) -> None:
    """Persist current verificationCriteria hashes to baseline."""
    hashes = {rid: req.criteria_hash for rid, req in requirements.items()}
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hashes": hashes,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    LOG.info("Baseline written to %s (%d entries)", path, len(hashes))


def detect_drift(
    requirements: dict[str, Requirement], baseline: dict[str, str]
) -> list[Requirement]:
    """Return requirements whose verificationCriteria hash differs from baseline."""
    drifted: list[Requirement] = []
    for rid, req in requirements.items():
        old_hash = baseline.get(rid)
        if old_hash is not None and old_hash != req.criteria_hash:
            drifted.append(req)
    return drifted


def inject_review_tag(feature_file: Path, req_id: str) -> bool:
    """Add @REVIEW_REQUIRED tag to scenarios in *feature_file* tagged with *req_id*.

    Returns True if any modification was made.
    """
    text = feature_file.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    modified = False

    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for a tag line that references the drifted requirement.
        if TAG_LINE_RE.match(line) and re.search(
            rf"@REQ[:\-_]{re.escape(req_id)}\b", line
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
            "Injected @REVIEW_REQUIRED into %s for requirement %s",
            feature_file,
            req_id,
        )

    return modified


# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------
def run_gate_a(
    requirements: dict[str, Requirement],
    covered_ids: set[str],
    stubs_output_dir: Path,
    non_test_output_dir: Path | None,
    template_path: Path | None,
    fail_on_uncovered: bool,
) -> GateResult:
    """Gate A — Uncovered Requirements."""
    uncovered_reqs = [
        req
        for rid, req in sorted(requirements.items())
        if rid not in covered_ids
    ]

    if not uncovered_reqs:
        return GateResult(
            gate="A",
            passed=True,
            message="All requirements are covered by at least one scenario.",
        )

    stubs = generate_stubs(
        uncovered_reqs, stubs_output_dir, non_test_output_dir, template_path
    )

    items = [
        {
            "requirementId": req.requirement_id,
            "title": req.title,
            "verificationMethod": req.verification_method,
            "stubGenerated": str(stub),
        }
        for req, stub in zip(uncovered_reqs, stubs)
    ]

    passed = not fail_on_uncovered
    msg = (
        f"{len(uncovered_reqs)} uncovered requirement(s) found; "
        f"{len(stubs)} stub(s) generated."
    )
    LOG.warning("Gate A: %s", msg)

    return GateResult(gate="A", passed=passed, items=items, message=msg)


def run_gate_b(
    requirements: dict[str, Requirement],
    scenario_refs: list[ScenarioRef],
    baseline: dict[str, str],
) -> GateResult:
    """Gate B — Verification Criteria Drift."""
    if not baseline:
        return GateResult(
            gate="B",
            passed=True,
            message="No baseline found; skipping drift detection. Run with --update-baseline to create one.",
        )

    drifted = detect_drift(requirements, baseline)

    if not drifted:
        return GateResult(
            gate="B",
            passed=True,
            message="No verification-criteria drift detected.",
        )

    # Build a lookup: req_id → list of feature files.
    req_to_files: dict[str, set[Path]] = {}
    for ref in scenario_refs:
        for rid in ref.req_ids:
            req_to_files.setdefault(rid, set()).add(ref.feature_file)

    items: list[dict[str, Any]] = []
    files_modified: set[Path] = set()
    for req in drifted:
        affected_files = req_to_files.get(req.requirement_id, set())
        for ff in affected_files:
            if inject_review_tag(ff, req.requirement_id):
                files_modified.add(ff)

        items.append(
            {
                "requirementId": req.requirement_id,
                "title": req.title,
                "oldHash": baseline.get(req.requirement_id, ""),
                "newHash": req.criteria_hash,
                "affectedFeatureFiles": [str(f) for f in sorted(affected_files)],
            }
        )

    msg = (
        f"{len(drifted)} requirement(s) with drifted verificationCriteria; "
        f"@REVIEW_REQUIRED injected into {len(files_modified)} file(s)."
    )
    LOG.warning("Gate B: %s", msg)

    # Drift causes pipeline failure — forces human review of changed criteria.
    # Developer must update scenarios, remove @REVIEW_REQUIRED, and run --update-baseline.
    return GateResult(gate="B", passed=False, items=items, message=msg)


def run_gate_c(
    requirements: dict[str, Requirement],
    scenario_refs: list[ScenarioRef],
    fail_on_orphaned: bool,
) -> GateResult:
    """Gate C — Orphaned Scenarios."""
    orphans: list[dict[str, Any]] = []
    for ref in scenario_refs:
        missing = [rid for rid in ref.req_ids if rid not in requirements]
        if missing:
            orphans.append(
                {
                    "featureFile": str(ref.feature_file),
                    "scenarioName": ref.scenario_name,
                    "lineNumber": ref.line_number,
                    "orphanedReqIds": missing,
                }
            )

    if not orphans:
        return GateResult(
            gate="C",
            passed=True,
            message="No orphaned scenarios detected.",
        )

    passed = not fail_on_orphaned
    msg = (
        f"{len(orphans)} scenario(s) reference requirement(s) that no longer exist."
    )
    LOG.warning("Gate C: %s", msg)

    return GateResult(gate="C", passed=passed, items=orphans, message=msg)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def build_report(
    requirements: dict[str, Requirement],
    features_dir: Path,
    gate_a: GateResult,
    gate_b: GateResult,
    gate_c: GateResult,
) -> TraceabilityReport:
    feature_count = sum(1 for _ in features_dir.rglob("*.feature"))
    overall = gate_a.passed and gate_b.passed and gate_c.passed

    return TraceabilityReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        requirements_total=len(requirements),
        features_scanned=feature_count,
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
        help="Directory for non-Test verification method stubs (default: stubs-output-dir/non_test).",
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
        help="Exit with code 1 if uncovered requirements are found.",
    )
    p.add_argument(
        "--fail-on-orphaned",
        action="store_true",
        help="Exit with code 1 if orphaned scenarios are found.",
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
    scenario_refs, covered_ids = scan_features(args.features_dir)

    # --- Load baseline --------------------------------------------------------
    baseline = load_baseline(args.baseline_path)

    # --- Resolve Jinja2 template path -----------------------------------------
    template_path = Path(__file__).resolve().parent / "templates" / "stub_scenario.feature.j2"

    # --- Run gates ------------------------------------------------------------
    gate_a = run_gate_a(
        requirements=requirements,
        covered_ids=covered_ids,
        stubs_output_dir=args.stubs_output_dir,
        non_test_output_dir=args.non_test_output_dir,
        template_path=template_path,
        fail_on_uncovered=args.fail_on_uncovered,
    )

    gate_b = run_gate_b(
        requirements=requirements,
        scenario_refs=scenario_refs,
        baseline=baseline,
    )

    gate_c = run_gate_c(
        requirements=requirements,
        scenario_refs=scenario_refs,
        fail_on_orphaned=args.fail_on_orphaned,
    )

    # --- Update baseline after drift check ------------------------------------
    save_baseline(args.baseline_path, requirements)

    # --- Build and write reports ----------------------------------------------
    report = build_report(requirements, args.features_dir, gate_a, gate_b, gate_c)

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

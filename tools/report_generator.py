#!/usr/bin/env python3
"""Generate the final traceability matrix report.

This script merges three data sources:

* **requirements.json** – the Cameo model export produced by the
  cameo-model-pipeline.
* **behave-results.json** – the JSON output from a Behave test run.
* **traceability_report.json** – the intermediate report produced by
  ``traceability_checker.py`` (lists covered, uncovered, drifted, and
  orphaned items).

It produces:

1. A **JSON report** containing a summary block and per-requirement detail.
2. An **HTML report** with a dashboard header, coverage bar, colour-coded
   table, and client-side filters.

Typical CLI usage::

    python report_generator.py \
        --requirements build/requirements.json \
        --behave-results build/behave-results.json \
        --traceability-input build/traceability_report.json \
        --output-json build/traceability_matrix.json \
        --output-html build/traceability_matrix.html
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / inline HTML fallback
# ---------------------------------------------------------------------------

_JINJA2_TEMPLATE_NAME = "traceability_report.html.j2"

_INLINE_HTML_TEMPLATE = textwrap.dedent(
    """\
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8"><title>Traceability Report</title>
    <style>
      body {{ font-family: sans-serif; margin: 2em; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; font-size: 0.9rem; }}
      th {{ background: #343a40; color: #fff; }}
      .pass {{ background: #d4edda; }}
      .fail, .uncovered {{ background: #f8d7da; }}
      .drifted {{ background: #fff3cd; }}
      .manual {{ background: #e2e3e5; }}
      .orphaned {{ background: #cce5ff; }}
      h1 {{ margin-bottom: 0.25em; }}
      .summary {{ margin-bottom: 1.5em; }}
    </style>
    </head>
    <body>
    <h1>Traceability Matrix Report</h1>
    <p>Generated: {generated_at}</p>
    <div class="summary">
      <p><strong>Requirements:</strong> {total} &nbsp;
         <strong>VCs:</strong> {total_vms} &nbsp;
         <strong>Covered VCs:</strong> {covered_vms} &nbsp;
         <strong>Uncovered VCs:</strong> {uncovered_vms} &nbsp;
         <strong>Drifted VCs:</strong> {drifted_vms} &nbsp;
         <strong>Orphaned Tests:</strong> {orphaned} &nbsp;
         <strong>Passed:</strong> {passed} &nbsp;
         <strong>Failed:</strong> {failed} &nbsp;
         <strong>Coverage:</strong> {coverage:.1f}%</p>
    </div>
    <table>
    <thead><tr>
      <th>Requirement ID</th><th>VM ID</th><th>Title</th><th>Method</th>
      <th>Priority</th><th>Status</th><th>Test Result</th><th>Feature File</th>
    </tr></thead>
    <tbody>
    {rows}
    </tbody>
    </table>
    </body>
    </html>
    """
)

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Dict[str, Any]:
    """Load a JSON file and return the parsed object."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _index_requirements(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return a dict mapping ``requirementId`` to each requirement record."""
    return {r["requirementId"]: r for r in data.get("requirements", [])}


def _index_behave_results(
    data: Any,
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Build lookups from requirement ID and VM ID to Behave scenario result.

    The Behave JSON report is a list of feature objects.  We look for tags
    matching known requirement ID patterns (e.g. ``SYS-REQ-001``) and VM ID
    patterns (e.g. ``SYS-REQ-001-VM-01``) and map them to their scenario
    result.

    Returns a tuple ``(req_result_map, vm_result_map)`` where each dict is
    keyed by the respective ID with values containing keys:
    ``status`` (passed / failed), ``feature_file``, ``name``.
    """
    req_result_map: Dict[str, Dict[str, Any]] = {}
    vm_result_map: Dict[str, Dict[str, Any]] = {}

    if isinstance(data, list):
        features = data
    elif isinstance(data, dict):
        features = data.get("features", data.get("results", []))
    else:
        return req_result_map, vm_result_map

    for feature in features:
        feature_file = feature.get("location", feature.get("filename", ""))

        # Collect feature-level tags (inherited by all scenarios)
        feature_req_tags = _extract_req_ids_from_tags(feature.get("tags", []))
        feature_vm_tags = _extract_vm_ids_from_tags(feature.get("tags", []))

        for element in feature.get("elements", []):
            # Collect scenario-level tags
            scenario_req_tags = _extract_req_ids_from_tags(element.get("tags", []))
            scenario_vm_tags = _extract_vm_ids_from_tags(element.get("tags", []))
            # Merge: scenario tags + inherited feature tags
            all_req_tags = scenario_req_tags | feature_req_tags
            all_vm_tags = scenario_vm_tags | feature_vm_tags

            # Determine overall scenario status
            steps = element.get("steps", [])
            scenario_status = "passed"
            for step in steps:
                step_result = step.get("result", {})
                if step_result.get("status") in ("failed", "undefined"):
                    scenario_status = "failed"
                    break

            scenario_name = element.get("name", "")

            result_entry = {
                "status": scenario_status,
                "feature_file": feature_file,
                "name": scenario_name,
            }

            for req_id in all_req_tags:
                req_result_map[req_id] = result_entry

            for vm_id in all_vm_tags:
                vm_result_map[vm_id] = result_entry

    return req_result_map, vm_result_map


def _parse_traceability_data(
    trace_data: Dict[str, Any],
    all_vm_ids: set[str],
) -> tuple[set[str], set[str], set[str], List[Dict[str, Any]]]:
    """Extract covered/uncovered/drifted/orphaned VM IDs from the traceability report.

    Supports two formats:

    1. **Gate-based** (from ``traceability_checker.py``): uses ``gate_a``,
       ``gate_b``, ``gate_c`` sub-objects.  Gate items may contain
       ``verificationMethodId`` / ``vm_id`` keys for VM-level granularity,
       falling back to ``requirementId`` for backwards compatibility.
    2. **Flat** (simpler): uses top-level ``covered``, ``uncovered``,
       ``drifted``, ``orphaned`` lists.

    Returns
    -------
    tuple
        ``(covered_ids, uncovered_ids, drifted_ids, orphaned_tests)``
        where the ID sets contain VM IDs when available, otherwise
        requirement IDs.
    """
    # --- Flat format ---
    if "covered" in trace_data or "uncovered" in trace_data:
        covered_ids: set[str] = set(trace_data.get("covered", []))
        uncovered_ids: set[str] = set(trace_data.get("uncovered", []))
        drifted_ids: set[str] = set(trace_data.get("drifted", []))
        orphaned_tests: List[Dict[str, Any]] = trace_data.get("orphaned", [])
        return covered_ids, uncovered_ids, drifted_ids, orphaned_tests

    # --- Gate-based format ---
    def _extract_id(item: Dict[str, Any]) -> str:
        """Extract the best available ID from a gate item (prefer VM ID)."""
        vm_id = item.get("verificationMethodId", item.get("vm_id", ""))
        if vm_id:
            return vm_id
        return item.get("requirementId", item.get("requirement_id", ""))

    def _as_dict(val: Any) -> Dict[str, Any]:
        return val if isinstance(val, dict) else {}

    uncovered_ids_gate: set[str] = set()
    gate_a = _as_dict(trace_data.get("gate_a"))
    for item in gate_a.get("items", []):
        extracted = _extract_id(item)
        if extracted:
            uncovered_ids_gate.add(extracted)

    drifted_ids_gate: set[str] = set()
    gate_b = _as_dict(trace_data.get("gate_b"))
    for item in gate_b.get("items", []):
        extracted = _extract_id(item)
        if extracted:
            drifted_ids_gate.add(extracted)

    orphaned_tests_gate: List[Dict[str, Any]] = []
    gate_c = _as_dict(trace_data.get("gate_c"))
    for item in gate_c.get("items", []):
        orphaned_tests_gate.append({
            "feature_file": item.get("featureFile", item.get("feature_file", "")),
            "name": item.get("scenarioName", item.get("name", "")),
            "orphaned_req_ids": item.get("orphanedReqIds", item.get("orphaned_req_ids", [])),
        })

    covered_ids_gate = all_vm_ids - uncovered_ids_gate
    return covered_ids_gate, uncovered_ids_gate, drifted_ids_gate, orphaned_tests_gate


def _extract_req_ids_from_tags(tags: list) -> set[str]:
    """Extract requirement IDs from a list of Behave JSON tags.

    Tags may be strings or dicts with a 'name' key.  Handles formats like:
    ``@REQ:SYS-REQ-001``, ``REQ:SYS-REQ-001``, or plain ``SYS-REQ-001``.
    """
    req_ids: set[str] = set()
    for t in tags:
        tag_str = t if isinstance(t, str) else t.get("name", "")
        tag_str = tag_str.lstrip("@")
        # Strip REQ: / REQ- / REQ_ prefix
        stripped = re.sub(r"^REQ[:\-_]", "", tag_str, flags=re.IGNORECASE)
        if _is_requirement_id(stripped):
            req_ids.add(stripped)
    return req_ids


def _is_requirement_id(tag: str) -> bool:
    """Return *True* if *tag* looks like a requirement ID (e.g. SYS-REQ-001)."""
    return bool(re.match(r"^[A-Z]+-[A-Z]+-\d{3,}$", tag))


def _extract_vm_ids_from_tags(tags: list) -> set[str]:
    """Extract verification-method IDs from a list of Behave JSON tags.

    Tags may be strings or dicts with a 'name' key.  Handles formats like:
    ``@VM:SYS-REQ-001-VM-01``, ``VM:SYS-REQ-001-VM-01``, or plain
    ``SYS-REQ-001-VM-01``.
    """
    vm_ids: set[str] = set()
    for t in tags:
        tag_str = t if isinstance(t, str) else t.get("name", "")
        tag_str = tag_str.lstrip("@")
        stripped = re.sub(r"^VM[:\-_]", "", tag_str, flags=re.IGNORECASE)
        if _is_vm_id(stripped):
            vm_ids.add(stripped)
    return vm_ids


def _is_vm_id(tag: str) -> bool:
    """Return *True* if *tag* looks like a VM ID (e.g. SYS-REQ-001-VM-01)."""
    return bool(re.match(r"^[A-Z]+-[A-Z]+-\d{3,}-VM-\d{2,}$", tag))


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------


def build_report(
    requirements_path: Path,
    behave_results_path: Path,
    traceability_input_path: Path,
) -> Dict[str, Any]:
    """Merge all data sources and produce the traceability report dict.

    Parameters
    ----------
    requirements_path:
        Path to the Cameo ``requirements.json``.
    behave_results_path:
        Path to the Behave ``behave-results.json``.
    traceability_input_path:
        Path to the ``traceability_report.json`` from
        ``traceability_checker.py``.

    Returns
    -------
    dict
        A report dict with ``summary``, ``requirements``, and
        ``orphaned_tests`` keys.
    """
    req_data = _load_json(requirements_path)
    req_index = _index_requirements(req_data)

    behave_data = _load_json(behave_results_path)
    req_behave_index, vm_behave_index = _index_behave_results(behave_data)

    trace_data = _load_json(traceability_input_path)

    # Build the set of all VM IDs across all requirements
    all_vm_ids: set[str] = set()
    for req in req_index.values():
        for vm in req.get("verificationMethods", []):
            vm_id = vm.get("verificationMethodId", "")
            if vm_id:
                all_vm_ids.add(vm_id)

    # Extract traceability data.  The traceability_checker.py emits a
    # gate-based format (gate_a, gate_b, gate_c) while a simpler format
    # with flat "covered"/"uncovered"/"drifted"/"orphaned" keys is also
    # supported for flexibility.
    covered_ids, uncovered_ids, drifted_ids, orphaned_tests = _parse_traceability_data(
        trace_data, all_vm_ids
    )

    # Manual verification methods don't have automated test results
    manual_methods = {"Analysis", "Inspection"}

    total_requirements = len(req_index)
    total_vms = 0
    passed = 0
    failed = 0
    manual_count = 0
    rows: List[Dict[str, Any]] = []

    for req_id, req in req_index.items():
        verification_methods = req.get("verificationMethods", [])

        # If no verificationMethods array, produce a single row using
        # legacy fields for backwards compatibility
        if not verification_methods:
            verification_methods = [{
                "verificationMethodId": "",
                "method": req.get("verificationMethod", "Test"),
                "criteria": req.get("verificationCriteria", ""),
            }]

        for vm in verification_methods:
            total_vms += 1
            vm_id: str = vm.get("verificationMethodId", "")
            method: str = vm.get("method", "Test")
            criteria: str = vm.get("criteria", "")
            is_manual = method in manual_methods

            # The lookup key for traceability is the VM ID when available
            lookup_id = vm_id or req_id

            # Determine row status FIRST — this controls whether we
            # look up Behave results (uncovered/drifted VMs should NOT
            # inherit test results from sibling VMs via req-level fallback)
            if lookup_id in drifted_ids:
                status = "drifted"
            elif lookup_id in uncovered_ids:
                status = "uncovered"
            elif is_manual:
                status = "manual"
                manual_count += 1
            else:
                # Only look up Behave results for covered, non-manual VMs
                behave_result = vm_behave_index.get(vm_id) if vm_id else None
                if behave_result is None:
                    behave_result = req_behave_index.get(req_id)

                if behave_result is not None:
                    status = "pass" if behave_result["status"] == "passed" else "fail"
                    if status == "pass":
                        passed += 1
                    else:
                        failed += 1
                else:
                    # Covered according to traceability but no Behave result found
                    status = "uncovered"

            # Only attach Behave data for VMs that actually have test results
            behave_result_for_row = None
            if status in ("pass", "fail"):
                behave_result_for_row = vm_behave_index.get(vm_id) if vm_id else None
                if behave_result_for_row is None:
                    behave_result_for_row = req_behave_index.get(req_id)

            row: Dict[str, Any] = {
                "requirement_id": req_id,
                "vm_id": vm_id,
                "title": req.get("title", ""),
                "method": method,
                "criteria": criteria,
                "priority": req.get("priority", ""),
                "status": status,
                "test_result": behave_result_for_row["status"] if behave_result_for_row else None,
                "feature_file": behave_result_for_row["feature_file"] if behave_result_for_row else None,
                "scenario_name": behave_result_for_row["name"] if behave_result_for_row else None,
            }
            rows.append(row)

    covered_count = len(covered_ids)
    uncovered_count = len(uncovered_ids)
    drifted_count = len(drifted_ids)
    coverage_percent = (covered_count / total_vms * 100) if total_vms > 0 else 0.0

    summary: Dict[str, Any] = {
        "total_requirements": total_requirements,
        "total_vms": total_vms,
        "covered_vms": covered_count,
        "uncovered_vms": uncovered_count,
        "drifted_vms": drifted_count,
        "orphaned_tests": len(orphaned_tests),
        "passed": passed,
        "failed": failed,
        "manual": manual_count,
        "coverage_percent": round(coverage_percent, 2),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "requirements": rows,
        "orphaned_tests": orphaned_tests,
    }


# ---------------------------------------------------------------------------
# Output renderers
# ---------------------------------------------------------------------------


def write_json_report(report: Dict[str, Any], output_path: Path) -> None:
    """Write the report dict as formatted JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    logger.info("JSON report written to %s", output_path)


def _try_load_jinja2_template(template_dir: Optional[Path] = None):
    """Attempt to load the Jinja2 HTML template; return *None* on failure."""
    try:
        from jinja2 import Environment, FileSystemLoader  # type: ignore[import-untyped]
    except ImportError:
        logger.debug("Jinja2 not installed – using inline HTML template.")
        return None

    if template_dir is None:
        template_dir = Path(__file__).resolve().parent / "templates"

    if not (template_dir / _JINJA2_TEMPLATE_NAME).is_file():
        logger.debug(
            "HTML template %s not found in %s – using inline template.",
            _JINJA2_TEMPLATE_NAME,
            template_dir,
        )
        return None

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        keep_trailing_newline=True,
    )
    return env.get_template(_JINJA2_TEMPLATE_NAME)


def _load_optional_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    """Load a JSON file if the path is provided and exists; return *None* otherwise."""
    if path is None:
        return None
    if not path.is_file():
        logger.warning("Optional file not found (skipping): %s", path)
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not load optional file %s: %s", path, exc)
        return None


def write_html_report(
    report: Dict[str, Any],
    output_path: Path,
    *,
    template_dir: Optional[Path] = None,
    requirements_raw: Optional[Dict[str, Any]] = None,
    behave_raw: Optional[Any] = None,
    traceability_raw: Optional[Dict[str, Any]] = None,
    sbom_data: Optional[Dict[str, Any]] = None,
    grype_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Render and write the HTML traceability report.

    Parameters
    ----------
    report:
        The merged report dict produced by :func:`build_report`.
    output_path:
        Destination for the HTML file.
    template_dir:
        Override directory for Jinja2 templates.
    requirements_raw:
        The full Cameo requirements export (with ``exportMetadata``).
    behave_raw:
        The raw Behave JSON results (with step-level detail).
    traceability_raw:
        The raw traceability report from ``traceability_checker.py``.
    sbom_data:
        Optional CycloneDX SBOM JSON from Syft.
    grype_data:
        Optional Grype vulnerability scan results JSON.
    """
    jinja_template = _try_load_jinja2_template(template_dir)

    if jinja_template is not None:
        # Escape </script> sequences in JSON to prevent XSS when
        # injecting data into <script> tags.  The standard trick is
        # to replace "</" with "<\\/" which is valid JSON/JS but
        # won't close an HTML script block.
        def _safe_json(obj: Any) -> str:
            return json.dumps(obj, ensure_ascii=False).replace("</", r"<\/")

        try:
            html = jinja_template.render(
                generated_at=report["generated_at"],
                summary=report["summary"],
                rows=report["requirements"],
                orphaned_tests=report.get("orphaned_tests", []),
                report_json=_safe_json(report),
                requirements_json=_safe_json(requirements_raw),
                behave_json=_safe_json(behave_raw),
                traceability_json=_safe_json(traceability_raw),
                sbom_json=_safe_json(sbom_data),
                grype_json=_safe_json(grype_data),
            )
        except Exception as exc:
            logger.warning(
                "Jinja2 template rendering failed (%s); falling back to inline template.",
                exc,
            )
            html = _render_inline_html(report)
    else:
        html = _render_inline_html(report)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("HTML report written to %s", output_path)


def _render_inline_html(report: Dict[str, Any]) -> str:
    """Render the report using the built-in inline HTML template."""
    summary = report["summary"]

    row_lines: List[str] = []
    for row in report["requirements"]:
        css_class = row["status"]
        row_lines.append(
            f'<tr class="{css_class}">'
            f'<td>{row["requirement_id"]}</td>'
            f'<td>{row.get("vm_id") or "—"}</td>'
            f'<td>{row["title"]}</td>'
            f'<td>{row.get("method") or "—"}</td>'
            f'<td>{row.get("priority") or "—"}</td>'
            f'<td>{row["status"]}</td>'
            f'<td>{row.get("test_result") or "—"}</td>'
            f'<td>{row.get("feature_file") or "—"}</td>'
            f"</tr>"
        )

    for orphan in report.get("orphaned_tests", []):
        name = orphan.get("name", orphan.get("feature_file", ""))
        result = orphan.get("result", "—")
        feature = orphan.get("feature_file", "—")
        row_lines.append(
            f'<tr class="orphaned">'
            f"<td>—</td>"
            f"<td>—</td>"
            f"<td>{name}</td>"
            f"<td>—</td>"
            f"<td>—</td>"
            f"<td>orphaned</td>"
            f"<td>{result}</td>"
            f"<td>{feature}</td>"
            f"</tr>"
        )

    return _INLINE_HTML_TEMPLATE.format(
        generated_at=report["generated_at"],
        total=summary["total_requirements"],
        total_vms=summary["total_vms"],
        covered_vms=summary["covered_vms"],
        uncovered_vms=summary["uncovered_vms"],
        drifted_vms=summary["drifted_vms"],
        orphaned=summary["orphaned_tests"],
        passed=summary["passed"],
        failed=summary["failed"],
        coverage=summary["coverage_percent"],
        rows="\n".join(row_lines),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate the traceability matrix report (JSON + HTML).",
    )
    parser.add_argument(
        "--requirements",
        required=True,
        type=Path,
        help="Path to the Cameo requirements.json export.",
    )
    parser.add_argument(
        "--behave-results",
        required=True,
        type=Path,
        help="Path to behave-results.json from the Behave test run.",
    )
    parser.add_argument(
        "--traceability-input",
        required=True,
        type=Path,
        help="Path to traceability_report.json from traceability_checker.py.",
    )
    parser.add_argument(
        "--output-json",
        required=True,
        type=Path,
        help="Output path for the JSON traceability matrix report.",
    )
    parser.add_argument(
        "--output-html",
        required=True,
        type=Path,
        help="Output path for the HTML traceability matrix report.",
    )
    parser.add_argument(
        "--template-dir",
        type=Path,
        default=None,
        help="Override directory containing Jinja2 templates.",
    )
    parser.add_argument(
        "--sbom-path",
        type=Path,
        default=None,
        help="Optional path to CycloneDX SBOM JSON (from Syft).",
    )
    parser.add_argument(
        "--grype-path",
        type=Path,
        default=None,
        help="Optional path to Grype vulnerability scan results JSON.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for CLI invocation.

    Returns
    -------
    int
        ``0`` on success, ``1`` on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    # Validate inputs
    for label, path in [
        ("Requirements", args.requirements),
        ("Behave results", args.behave_results),
        ("Traceability input", args.traceability_input),
    ]:
        if not path.is_file():
            logger.error("%s file not found: %s", label, path)
            return 1

    report = build_report(
        requirements_path=args.requirements,
        behave_results_path=args.behave_results,
        traceability_input_path=args.traceability_input,
    )

    # Load raw data for the interactive dashboard template
    requirements_raw = _load_json(args.requirements)
    behave_raw = _load_json(args.behave_results)
    traceability_raw = _load_json(args.traceability_input)
    sbom_data = _load_optional_json(getattr(args, "sbom_path", None))
    grype_data = _load_optional_json(getattr(args, "grype_path", None))

    write_json_report(report, args.output_json)
    write_html_report(
        report,
        args.output_html,
        template_dir=args.template_dir,
        requirements_raw=requirements_raw,
        behave_raw=behave_raw,
        traceability_raw=traceability_raw,
        sbom_data=sbom_data,
        grype_data=grype_data,
    )

    summary = report["summary"]
    logger.info(
        "Report complete: %d requirements, %d VCs, %.1f%% coverage, %d passed, %d failed.",
        summary["total_requirements"],
        summary["total_vms"],
        summary["coverage_percent"],
        summary["passed"],
        summary["failed"],
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())

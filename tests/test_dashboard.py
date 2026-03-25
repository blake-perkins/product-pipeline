#!/usr/bin/env python3
"""Comprehensive tests for the traceability dashboard.

Tests cover:
- report_generator.py data merging logic
- HTML dashboard rendering and data injection
- Scenario-to-VC matching accuracy
- Status assignment correctness
- Edge cases (uncovered, drifted, manual, orphaned)
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

# Ensure tools/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import report_generator  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures: realistic test data matching real feature files
# ---------------------------------------------------------------------------

REQUIREMENTS_DATA = {
    "exportMetadata": {
        "exportTimestamp": "2026-03-10T14:30:00Z",
        "cameoVersion": "2024x Refresh2",
        "projectName": "SampleSystem",
        "modelVersion": "0.2.0",
    },
    "requirements": [
        {
            "requirementId": "SYS-REQ-001",
            "title": "Basic ICD Communications",
            "description": "The system shall exchange messages with external systems.",
            "priority": "High",
            "status": "Approved",
            "parentRequirementId": None,
            "verificationCriteria": [
                {"verificationCriteriaId": "SYS-REQ-001-VC-01", "method": "Test",
                 "criteria": "Verify valid IcdRequest produces valid IcdResponse within 500ms."},
                {"verificationCriteriaId": "SYS-REQ-001-VC-02", "method": "Demonstration",
                 "criteria": "Demonstrate round-trip ICD exchange with simulator."},
            ],
            "satisfiedBy": ["ComponentA"],
            "tracesTo": [],
        },
        {
            "requirementId": "SYS-REQ-002",
            "title": "Health Monitoring",
            "description": "The system shall report health status.",
            "priority": "High",
            "status": "Approved",
            "parentRequirementId": None,
            "verificationCriteria": [
                {"verificationCriteriaId": "SYS-REQ-002-VC-01", "method": "Test",
                 "criteria": "Verify health status messages emitted at interval."},
            ],
            "satisfiedBy": ["ComponentA"],
            "tracesTo": [],
        },
        {
            "requirementId": "SYS-REQ-004",
            "title": "Thermal Analysis Compliance",
            "description": "Operate within thermal envelope.",
            "priority": "Critical",
            "status": "Approved",
            "parentRequirementId": None,
            "verificationCriteria": [
                {"verificationCriteriaId": "SYS-REQ-004-VC-01", "method": "Analysis",
                 "criteria": "Thermal analysis confirms operating temperature range."},
            ],
            "satisfiedBy": [],
            "tracesTo": [],
        },
    ],
}


def _make_behave_scenario(name, status="passed", tags=None, steps=None):
    """Helper to build a Behave JSON scenario element."""
    if steps is None:
        steps = [
            {"keyword": "Given ", "name": "the simulation logs are loaded",
             "result": {"status": status, "duration": 0.001}},
            {"keyword": "Then ", "name": "some assertion",
             "result": {"status": status, "duration": 0.002}},
        ]
    return {
        "keyword": "Scenario",
        "name": name,
        "tags": tags or [],
        "type": "scenario",
        "status": status,
        "steps": steps,
    }


def _behave_all_covered():
    """Behave results where VC-01 and VC-02 both have proper @VC: tags."""
    return [
        {
            "keyword": "Feature",
            "name": "Basic ICD Communications",
            "tags": ["REQ:SYS-REQ-001"],
            "location": "features/automated/sys_req_001.feature",
            "status": "passed",
            "elements": [
                _make_behave_scenario(
                    "Valid ICD request produces correct response",
                    tags=["VC:SYS-REQ-001-VC-01", "VER:Test"],
                ),
                _make_behave_scenario(
                    "All ICD responses within latency threshold",
                    tags=["VC:SYS-REQ-001-VC-01", "VER:Test"],
                ),
                _make_behave_scenario(
                    "Demonstrate round-trip ICD exchange",
                    tags=["VC:SYS-REQ-001-VC-02", "VER:Demonstration"],
                ),
            ],
        },
        {
            "keyword": "Feature",
            "name": "Health Monitoring",
            "tags": ["REQ:SYS-REQ-002"],
            "location": "features/automated/sys_req_002.feature",
            "status": "passed",
            "elements": [
                _make_behave_scenario(
                    "Health status messages are emitted",
                    tags=["VC:SYS-REQ-002-VC-01", "VER:Test"],
                ),
            ],
        },
    ]


def _traceability_all_pass():
    """Gate results: all covered, no drift, no orphans."""
    return {
        "timestamp": "2026-03-10T15:00:00Z",
        "requirements_total": 3,
        "features_scanned": 3,
        "vms_total": 4,
        "vms_covered": 4,
        "gate_a": {"gate": "A", "passed": True, "items": [], "message": "All VCs covered."},
        "gate_b": {"gate": "B", "passed": True, "items": [], "message": "No drift."},
        "gate_c": {"gate": "C", "passed": True, "items": [], "message": "No orphans."},
        "overall_pass": True,
    }


def _traceability_with_uncovered():
    """Gate results: VC-02 is uncovered."""
    return {
        "timestamp": "2026-03-10T15:00:00Z",
        "requirements_total": 3,
        "features_scanned": 2,
        "vms_total": 4,
        "vms_covered": 3,
        "gate_a": {
            "gate": "A", "passed": False,
            "items": [{"verificationCriteriaId": "SYS-REQ-001-VC-02", "method": "Demonstration",
                        "title": "Basic ICD Communications", "stubGenerated": "stubs/vm02.feature"}],
            "message": "1 uncovered VC.",
        },
        "gate_b": {"gate": "B", "passed": True, "items": [], "message": "No drift."},
        "gate_c": {"gate": "C", "passed": True, "items": [], "message": "No orphans."},
        "overall_pass": False,
    }


def _behave_without_vc02():
    """Behave results missing VC-02 scenario (it's uncovered)."""
    return [
        {
            "keyword": "Feature",
            "name": "Basic ICD Communications",
            "tags": ["REQ:SYS-REQ-001"],
            "location": "features/automated/sys_req_001.feature",
            "status": "passed",
            "elements": [
                _make_behave_scenario(
                    "Valid ICD request produces correct response",
                    tags=["VC:SYS-REQ-001-VC-01", "VER:Test"],
                ),
            ],
        },
        {
            "keyword": "Feature",
            "name": "Health Monitoring",
            "tags": ["REQ:SYS-REQ-002"],
            "location": "features/automated/sys_req_002.feature",
            "status": "passed",
            "elements": [
                _make_behave_scenario(
                    "Health status messages are emitted",
                    tags=["VC:SYS-REQ-002-VC-01", "VER:Test"],
                ),
            ],
        },
    ]


def _write_json(tmpdir, name, data):
    """Write a JSON file and return its Path."""
    path = Path(tmpdir) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests: report_generator.build_report()
# ---------------------------------------------------------------------------


class TestBuildReport:
    """Tests for the core report building logic."""

    def _build(self, tmpdir, behave_data, trace_data, req_data=None):
        req_path = _write_json(tmpdir, "req.json", req_data or REQUIREMENTS_DATA)
        behave_path = _write_json(tmpdir, "behave.json", behave_data)
        trace_path = _write_json(tmpdir, "trace.json", trace_data)
        return report_generator.build_report(req_path, behave_path, trace_path)

    def test_all_covered_status(self, tmp_path):
        """When all VCs have scenarios, no VC should be uncovered."""
        report = self._build(tmp_path, _behave_all_covered(), _traceability_all_pass())
        summary = report["summary"]
        assert summary["total_vcs"] == 4
        assert summary["covered_vcs"] == 4
        assert summary["uncovered_vcs"] == 0
        assert summary["passed"] == 3  # Test + Demonstration VCs (not Analysis)
        assert summary["manual"] == 1  # Analysis VC
        assert summary["failed"] == 0

    def test_all_covered_vm_statuses(self, tmp_path):
        """Each VC row should have the correct status."""
        report = self._build(tmp_path, _behave_all_covered(), _traceability_all_pass())
        rows = {r["vc_id"]: r for r in report["requirements"]}

        assert rows["SYS-REQ-001-VC-01"]["status"] == "pass"
        assert rows["SYS-REQ-001-VC-02"]["status"] == "pass"
        assert rows["SYS-REQ-002-VC-01"]["status"] == "pass"
        assert rows["SYS-REQ-004-VC-01"]["status"] == "manual"

    def test_uncovered_vm_has_no_test_result(self, tmp_path):
        """An uncovered VC must NOT inherit test results from sibling VCs."""
        report = self._build(tmp_path, _behave_without_vc02(), _traceability_with_uncovered())
        rows = {r["vc_id"]: r for r in report["requirements"]}

        vc02 = rows["SYS-REQ-001-VC-02"]
        assert vc02["status"] == "uncovered"
        assert vc02["test_result"] is None, \
            f"Uncovered VC should have no test_result, got: {vm02['test_result']}"
        assert vc02["scenario_name"] is None, \
            f"Uncovered VC should have no scenario_name, got: {vm02['scenario_name']}"
        assert vc02["feature_file"] is None

    def test_uncovered_vm_does_not_inflate_pass_count(self, tmp_path):
        """Uncovered VCs should not count toward passed or failed."""
        report = self._build(tmp_path, _behave_without_vc02(), _traceability_with_uncovered())
        summary = report["summary"]
        assert summary["passed"] == 2  # VC-01 + REQ-002-VC-01
        assert summary["failed"] == 0
        assert summary["uncovered_vcs"] == 1

    def test_manual_vm_has_no_test_result(self, tmp_path):
        """Analysis/Inspection VCs should be 'manual' with no test result."""
        report = self._build(tmp_path, _behave_all_covered(), _traceability_all_pass())
        rows = {r["vc_id"]: r for r in report["requirements"]}

        vc_analysis = rows["SYS-REQ-004-VC-01"]
        assert vc_analysis["status"] == "manual"
        assert vc_analysis["test_result"] is None
        assert vc_analysis["scenario_name"] is None

    def test_vc_level_behave_matching(self, tmp_path):
        """When Behave has @VC: tags, each VC should get its own scenario."""
        report = self._build(tmp_path, _behave_all_covered(), _traceability_all_pass())
        rows = {r["vc_id"]: r for r in report["requirements"]}

        # VC-01 should match a VC-01 scenario (last one wins in current impl)
        vc01 = rows["SYS-REQ-001-VC-01"]
        assert vc01["scenario_name"] is not None
        assert vc01["test_result"] == "passed"

        # VC-02 should get the Demonstration scenario, not a VC-01 scenario
        vc02 = rows["SYS-REQ-001-VC-02"]
        assert vc02["scenario_name"] == "Demonstrate round-trip ICD exchange"

    def test_failed_scenario_status(self, tmp_path):
        """A failed Behave scenario should result in status 'fail'."""
        behave = [
            {
                "keyword": "Feature", "name": "ICD", "tags": ["REQ:SYS-REQ-001"],
                "location": "f.feature", "status": "failed",
                "elements": [
                    _make_behave_scenario("Failing test", status="failed",
                                          tags=["VC:SYS-REQ-001-VC-01"]),
                    _make_behave_scenario("Demo", tags=["VC:SYS-REQ-001-VC-02"]),
                ],
            },
            {
                "keyword": "Feature", "name": "Health", "tags": ["REQ:SYS-REQ-002"],
                "location": "h.feature", "status": "passed",
                "elements": [_make_behave_scenario("Health", tags=["VC:SYS-REQ-002-VC-01"])],
            },
        ]
        report = self._build(tmp_path, behave, _traceability_all_pass())
        rows = {r["vc_id"]: r for r in report["requirements"]}

        assert rows["SYS-REQ-001-VC-01"]["status"] == "fail"
        assert rows["SYS-REQ-001-VC-01"]["test_result"] == "failed"
        assert report["summary"]["failed"] == 1

    def test_coverage_percent_calculation(self, tmp_path):
        """Coverage should be covered_vcs / total_vcs * 100."""
        report = self._build(tmp_path, _behave_without_vc02(), _traceability_with_uncovered())
        summary = report["summary"]
        expected = 3 / 4 * 100  # 75%
        assert summary["coverage_percent"] == round(expected, 2)

    def test_drifted_vm_has_no_test_result(self, tmp_path):
        """Drifted VCs should not inherit test results."""
        trace = _traceability_all_pass()
        trace["gate_b"] = {
            "gate": "B", "passed": False,
            "items": [{"verificationCriteriaId": "SYS-REQ-001-VC-01",
                        "oldHash": "aaa", "newHash": "bbb"}],
            "message": "1 drifted.",
        }
        report = self._build(tmp_path, _behave_all_covered(), trace)
        rows = {r["vc_id"]: r for r in report["requirements"]}

        assert rows["SYS-REQ-001-VC-01"]["status"] == "drifted"
        assert rows["SYS-REQ-001-VC-01"]["test_result"] is None
        assert rows["SYS-REQ-001-VC-01"]["scenario_name"] is None


# ---------------------------------------------------------------------------
# Tests: HTML dashboard rendering
# ---------------------------------------------------------------------------


class TestHTMLDashboard:
    """Tests for the HTML dashboard output."""

    def _generate_html(self, tmpdir, behave_data=None, trace_data=None):
        """Generate the full HTML dashboard and return the HTML string."""
        req_data = REQUIREMENTS_DATA
        behave_data = behave_data or _behave_all_covered()
        trace_data = trace_data or _traceability_all_pass()

        req_path = _write_json(tmpdir, "req.json", req_data)
        behave_path = _write_json(tmpdir, "behave.json", behave_data)
        trace_path = _write_json(tmpdir, "trace.json", trace_data)

        report = report_generator.build_report(req_path, behave_path, trace_path)
        out_json = Path(tmpdir) / "report.json"
        out_html = Path(tmpdir) / "report.html"

        report_generator.write_json_report(report, out_json)
        report_generator.write_html_report(
            report, out_html,
            requirements_raw=req_data,
            behave_raw=behave_data,
            traceability_raw=trace_data,
            sbom_data=None,
            grype_data=None,
            release_plan_data=None,
        )
        return out_html.read_text(encoding="utf-8")

    def test_html_contains_all_tabs(self, tmp_path):
        """Dashboard should have all 7 tab panels."""
        html = self._generate_html(tmp_path)
        assert 'id="panel-summary"' in html
        assert 'id="panel-traceability"' in html
        assert 'id="panel-releases"' in html
        assert 'id="panel-security"' in html
        assert 'id="panel-gates"' in html
        assert 'id="panel-tests"' in html
        assert 'id="panel-export"' in html

    def test_html_data_injection(self, tmp_path):
        """All 6 data objects should be injected as JSON in script tags."""
        html = self._generate_html(tmp_path)
        assert "const REPORT = {" in html
        assert "const REQUIREMENTS = {" in html
        assert "const BEHAVE = [" in html
        assert "const TRACEABILITY = {" in html
        assert "const SBOM = null" in html
        assert "const GRYPE = null" in html

    def test_html_contains_requirement_ids(self, tmp_path):
        """All requirement IDs should appear in the injected data."""
        html = self._generate_html(tmp_path)
        assert "SYS-REQ-001" in html
        assert "SYS-REQ-002" in html
        assert "SYS-REQ-004" in html

    def test_html_contains_vc_ids(self, tmp_path):
        """All VC IDs should appear in the injected data."""
        html = self._generate_html(tmp_path)
        assert "SYS-REQ-001-VC-01" in html
        assert "SYS-REQ-001-VC-02" in html
        assert "SYS-REQ-002-VC-01" in html
        assert "SYS-REQ-004-VC-01" in html

    def test_html_coverage_metric(self, tmp_path):
        """Hero header should show correct coverage percentage."""
        html = self._generate_html(tmp_path)
        assert "100%" in html

    def test_html_security_empty_state(self, tmp_path):
        """When no SBOM/Grype data, security tab should show empty state."""
        html = self._generate_html(tmp_path)
        assert "Cyber Scan Data Not Included" in html

    def test_html_with_sbom_data(self, tmp_path):
        """When SBOM data is provided, it should be injected."""
        req_path = _write_json(tmp_path, "req.json", REQUIREMENTS_DATA)
        behave_path = _write_json(tmp_path, "behave.json", _behave_all_covered())
        trace_path = _write_json(tmp_path, "trace.json", _traceability_all_pass())

        report = report_generator.build_report(req_path, behave_path, trace_path)
        out_html = Path(tmp_path) / "report.html"

        sbom = {"components": [{"name": "libcurl", "version": "7.88", "type": "library", "purl": "pkg:deb/libcurl@7.88"}]}
        report_generator.write_html_report(
            report, out_html,
            requirements_raw=REQUIREMENTS_DATA,
            behave_raw=_behave_all_covered(),
            traceability_raw=_traceability_all_pass(),
            sbom_data=sbom,
            grype_data=None,
            release_plan_data=None,
        )
        html = out_html.read_text(encoding="utf-8")
        assert "const SBOM = {" in html
        assert "libcurl" in html

    def test_html_gate_data_present(self, tmp_path):
        """Gate status data should be in TRACEABILITY JSON."""
        html = self._generate_html(tmp_path)
        assert "gate_a" in html
        assert "gate_b" in html
        assert "gate_c" in html

    def test_html_behave_steps_present(self, tmp_path):
        """Behave step text should be in the injected data for drill-down."""
        html = self._generate_html(tmp_path)
        assert "the simulation logs are loaded" in html

    def test_html_no_external_resources(self, tmp_path):
        """Dashboard must be self-contained (air-gapped compatible)."""
        html = self._generate_html(tmp_path)
        # Should not contain any http:// or https:// URLs (except in data)
        # Check the <head> section specifically
        head_match = re.search(r"<head>(.*?)</head>", html, re.DOTALL)
        if head_match:
            head = head_match.group(1)
            assert "http://" not in head, "External HTTP resource in <head>"
            assert "https://" not in head, "External HTTPS resource in <head>"

    def test_html_uncovered_dashboard(self, tmp_path):
        """Dashboard with uncovered VCs should show blocker info."""
        html = self._generate_html(tmp_path, _behave_without_vc02(), _traceability_with_uncovered())
        assert "uncovered" in html.lower()
        assert "Attention Required" in html

    def test_html_model_metadata(self, tmp_path):
        """Export tab should contain model metadata from requirements."""
        html = self._generate_html(tmp_path)
        assert "0.2.0" in html  # modelVersion
        assert "SampleSystem" in html  # projectName


# ---------------------------------------------------------------------------
# Tests: tag extraction helpers
# ---------------------------------------------------------------------------


class TestTagExtraction:
    """Tests for tag parsing utilities."""

    def test_extract_req_ids_string_tags(self):
        tags = ["REQ:SYS-REQ-001", "VER:Test", "some-other-tag"]
        result = report_generator._extract_req_ids_from_tags(tags)
        assert result == {"SYS-REQ-001"}

    def test_extract_req_ids_dict_tags(self):
        tags = [{"name": "@REQ:SYS-REQ-001"}, {"name": "@VER:Test"}]
        result = report_generator._extract_req_ids_from_tags(tags)
        assert result == {"SYS-REQ-001"}

    def test_extract_vc_ids(self):
        tags = ["VC:SYS-REQ-001-VC-01", "VER:Test"]
        result = report_generator._extract_vc_ids_from_tags(tags)
        assert result == {"SYS-REQ-001-VC-01"}

    def test_extract_vc_ids_with_at_prefix(self):
        tags = ["@VC:SYS-REQ-001-VC-01"]
        result = report_generator._extract_vc_ids_from_tags(tags)
        assert result == {"SYS-REQ-001-VC-01"}

    def test_is_vc_id_valid(self):
        assert report_generator._is_vc_id("SYS-REQ-001-VC-01") is True
        assert report_generator._is_vc_id("SYS-REQ-001") is False
        assert report_generator._is_vc_id("not-a-vc") is False

    def test_is_requirement_id_valid(self):
        assert report_generator._is_requirement_id("SYS-REQ-001") is True
        assert report_generator._is_requirement_id("SYS-REQ-001-VC-01") is False


# ---------------------------------------------------------------------------
# Tests: Behave result indexing
# ---------------------------------------------------------------------------


class TestBehaveIndexing:
    """Tests for _index_behave_results correctness."""

    def test_vc_level_indexing(self):
        """Scenarios with @VC: tags should be indexed by VC ID."""
        behave = _behave_all_covered()
        req_map, vc_map = report_generator._index_behave_results(behave)

        assert "SYS-REQ-001-VC-01" in vc_map
        assert "SYS-REQ-001-VC-02" in vc_map
        assert "SYS-REQ-002-VC-01" in vc_map

    def test_req_level_indexing(self):
        """Feature-level @REQ: tags should index by requirement ID."""
        behave = _behave_all_covered()
        req_map, vc_map = report_generator._index_behave_results(behave)

        assert "SYS-REQ-001" in req_map
        assert "SYS-REQ-002" in req_map

    def test_vc_index_gets_correct_scenario(self):
        """VC-02 should be mapped to the Demonstration scenario, not VC-01."""
        behave = _behave_all_covered()
        _, vc_map = report_generator._index_behave_results(behave)

        assert vc_map["SYS-REQ-001-VC-02"]["name"] == "Demonstrate round-trip ICD exchange"

    def test_feature_tag_inheritance(self):
        """Scenarios inherit feature-level tags."""
        behave = [{
            "keyword": "Feature", "name": "Test",
            "tags": ["REQ:SYS-REQ-001"],
            "location": "test.feature",
            "elements": [{
                "keyword": "Scenario", "name": "S1",
                "tags": ["VC:SYS-REQ-001-VC-01"],
                "steps": [{"keyword": "Given ", "name": "x",
                           "result": {"status": "passed", "duration": 0.001}}],
                "status": "passed",
            }],
        }]
        req_map, vc_map = report_generator._index_behave_results(behave)
        # Both req and vc should be indexed
        assert "SYS-REQ-001" in req_map
        assert "SYS-REQ-001-VC-01" in vc_map


# ---------------------------------------------------------------------------
# Tests: traceability data parsing
# ---------------------------------------------------------------------------


class TestTraceabilityParsing:
    """Tests for _parse_traceability_data."""

    def test_gate_based_format(self):
        trace = _traceability_with_uncovered()
        all_vms = {"SYS-REQ-001-VC-01", "SYS-REQ-001-VC-02",
                    "SYS-REQ-002-VC-01", "SYS-REQ-004-VC-01"}
        covered, uncovered, drifted, orphaned, deferred, deferred_releases = report_generator._parse_traceability_data(
            trace, all_vms
        )
        assert "SYS-REQ-001-VC-02" in uncovered
        assert "SYS-REQ-001-VC-02" not in covered
        assert len(drifted) == 0
        assert len(orphaned) == 0
        assert len(deferred) == 0

    def test_flat_format(self):
        trace = {
            "covered": ["SYS-REQ-001-VC-01"],
            "uncovered": ["SYS-REQ-001-VC-02"],
            "drifted": [],
            "orphaned": [],
        }
        covered, uncovered, drifted, orphaned, deferred, deferred_releases = report_generator._parse_traceability_data(
            trace, set()
        )
        assert "SYS-REQ-001-VC-01" in covered
        assert "SYS-REQ-001-VC-02" in uncovered


# ---------------------------------------------------------------------------
# Tests: edge cases from audit
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases discovered during the deep audit."""

    def _build(self, tmpdir, behave_data, trace_data, req_data=None):
        req_path = _write_json(tmpdir, "req.json", req_data or REQUIREMENTS_DATA)
        behave_path = _write_json(tmpdir, "behave.json", behave_data)
        trace_path = _write_json(tmpdir, "trace.json", trace_data)
        return report_generator.build_report(req_path, behave_path, trace_path)

    def test_xss_script_tag_escaped(self, tmp_path):
        """JSON injection must escape </script> to prevent XSS."""
        # Create requirements with a </script> in the title
        req_data = {
            "exportMetadata": REQUIREMENTS_DATA["exportMetadata"],
            "requirements": [{
                "requirementId": "SYS-REQ-XSS",
                "title": "Test </script><script>alert('XSS')</script> attack",
                "description": "Malicious description",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [{
                    "verificationCriteriaId": "SYS-REQ-XSS-VC-01",
                    "method": "Test",
                    "criteria": "criteria",
                }],
                "satisfiedBy": [],
                "tracesTo": [],
            }],
        }
        req_path = _write_json(tmp_path, "req.json", req_data)
        behave_path = _write_json(tmp_path, "behave.json", [])
        trace_path = _write_json(tmp_path, "trace.json", _traceability_all_pass())

        report = report_generator.build_report(req_path, behave_path, trace_path)
        out_html = Path(tmp_path) / "report.html"
        report_generator.write_html_report(
            report, out_html,
            requirements_raw=req_data,
            behave_raw=[],
            traceability_raw=_traceability_all_pass(),
        )
        html = out_html.read_text(encoding="utf-8")
        # The raw </script> should NOT appear in the HTML
        assert "</script><script>" not in html
        # The escaped version should be present
        assert r"<\/script>" in html or "\\u003c/script>" in html.lower()

    def test_empty_behave_results(self, tmp_path):
        """Report should handle empty Behave results gracefully."""
        report = self._build(tmp_path, [], _traceability_all_pass())
        # All VCs should still exist, just without test results
        assert report["summary"]["total_vcs"] == 4
        assert report["summary"]["passed"] >= 0  # No crash

    def test_null_gate_values(self, tmp_path):
        """Null gate values in traceability should not crash."""
        trace = {
            "gate_a": None,
            "gate_b": None,
            "gate_c": None,
        }
        report = self._build(tmp_path, _behave_all_covered(), trace)
        # Should produce a valid report (all VCs covered since no gates report issues)
        assert report["summary"]["total_vcs"] == 4

    def test_missing_gate_keys(self, tmp_path):
        """Traceability report with no gate keys should not crash."""
        trace = {"timestamp": "2026-01-01"}
        report = self._build(tmp_path, _behave_all_covered(), trace)
        assert report["summary"]["total_vcs"] == 4

    def test_empty_verification_criteria_array(self, tmp_path):
        """A requirement with empty verificationCriteria [] should get a fallback row."""
        req_data = {
            "exportMetadata": REQUIREMENTS_DATA["exportMetadata"],
            "requirements": [{
                "requirementId": "SYS-REQ-EMPTY",
                "title": "Empty VCs",
                "description": "",
                "priority": "Low",
                "status": "Draft",
                "parentRequirementId": None,
                "verificationCriteria": [],
                "satisfiedBy": [],
                "tracesTo": [],
            }],
        }
        report = self._build(tmp_path, [], {"covered": [], "uncovered": [], "drifted": [], "orphaned": []}, req_data)
        assert report["summary"]["total_vcs"] == 1  # Fallback row created

    def test_optional_file_not_found(self, tmp_path):
        """_load_optional_json should return None for non-existent file."""
        result = report_generator._load_optional_json(Path(tmp_path) / "nonexistent.json")
        assert result is None

    def test_optional_file_none_path(self):
        """_load_optional_json should return None for None path."""
        result = report_generator._load_optional_json(None)
        assert result is None

    def test_optional_file_valid(self, tmp_path):
        """_load_optional_json should load valid JSON."""
        path = _write_json(tmp_path, "test.json", {"key": "value"})
        result = report_generator._load_optional_json(path)
        assert result == {"key": "value"}

    def test_optional_file_invalid_json(self, tmp_path):
        """_load_optional_json should return None for malformed JSON."""
        path = Path(tmp_path) / "bad.json"
        path.write_text("not json{{{", encoding="utf-8")
        result = report_generator._load_optional_json(path)
        assert result is None

    def test_html_dashboard_with_empty_behave(self, tmp_path):
        """Dashboard should render without crash when Behave data is empty."""
        req_path = _write_json(tmp_path, "req.json", REQUIREMENTS_DATA)
        behave_path = _write_json(tmp_path, "behave.json", [])
        trace_path = _write_json(tmp_path, "trace.json", _traceability_all_pass())

        report = report_generator.build_report(req_path, behave_path, trace_path)
        out_html = Path(tmp_path) / "report.html"
        report_generator.write_html_report(
            report, out_html,
            requirements_raw=REQUIREMENTS_DATA,
            behave_raw=[],
            traceability_raw=_traceability_all_pass(),
        )
        html = out_html.read_text(encoding="utf-8")
        assert "const BEHAVE = []" in html
        assert "No Behave test results available" in html


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))

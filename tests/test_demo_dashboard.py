#!/usr/bin/env python3
"""Exhaustive validation of the demo dashboard.

Generates demo data with all states (pass, fail, uncovered, drifted,
manual, orphaned) and validates every aspect of the rendered dashboard.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import generate_demo_data
import report_generator


def _extract_js_json(html, var_name):
    """Extract a JS variable's JSON value from the HTML."""
    pattern = f"const {var_name} = "
    start = html.index(pattern) + len(pattern)
    depth = 0
    i = start
    while i < len(html):
        c = html[i]
        if c in ("{", "["): depth += 1
        elif c in ("}", "]"): depth -= 1
        elif c == ";" and depth == 0: break
        elif c == "n" and html[i:i+4] == "null" and depth == 0:
            return None
        i += 1
    raw = html[start:i].replace(r"<\/", "</")
    return json.loads(raw)


class TestDemoDashboard:
    """Full end-to-end validation of demo dashboard."""

    @classmethod
    def setup_class(cls):
        """Generate demo data and render the dashboard once."""
        cls.tmpdir = Path("build/test_demo")
        generate_demo_data.generate(cls.tmpdir)

        cls.report = report_generator.build_report(
            cls.tmpdir / "requirements.json",
            cls.tmpdir / "behave-results.json",
            cls.tmpdir / "traceability_report.json",
        )

        cls.req_raw = json.loads((cls.tmpdir / "requirements.json").read_text(encoding="utf-8"))
        cls.behave_raw = json.loads((cls.tmpdir / "behave-results.json").read_text(encoding="utf-8"))
        cls.trace_raw = json.loads((cls.tmpdir / "traceability_report.json").read_text(encoding="utf-8"))

        html_path = cls.tmpdir / "dashboard.html"
        report_generator.write_json_report(cls.report, cls.tmpdir / "report.json")
        report_generator.write_html_report(
            cls.report, html_path,
            requirements_raw=cls.req_raw,
            behave_raw=cls.behave_raw,
            traceability_raw=cls.trace_raw,
        )
        cls.html = html_path.read_text(encoding="utf-8")

        # Extract injected data from HTML
        cls.js_report = _extract_js_json(cls.html, "REPORT")
        cls.js_reqs = _extract_js_json(cls.html, "REQUIREMENTS")
        cls.js_behave = _extract_js_json(cls.html, "BEHAVE")
        cls.js_trace = _extract_js_json(cls.html, "TRACEABILITY")
        cls.js_sbom = _extract_js_json(cls.html, "SBOM")
        cls.js_grype = _extract_js_json(cls.html, "GRYPE")

        cls.rows = {r["vm_id"]: r for r in cls.report["requirements"]}
        cls.summary = cls.report["summary"]

    # ---- HERO HEADER ----

    def test_hero_coverage_percent(self):
        # Coverage is against in-scope VMs only (7 in-scope, all covered = 100%)
        assert self.summary["coverage_percent"] == 100.0

    def test_hero_total_vms(self):
        assert self.summary["total_vms"] == 8

    def test_hero_covered_vms(self):
        assert self.summary["covered_vms"] == 7

    def test_hero_passed(self):
        assert self.summary["passed"] == 3

    def test_hero_failed(self):
        assert self.summary["failed"] == 1

    def test_hero_uncovered(self):
        # SYS-REQ-003-VM-02 is now deferred, not uncovered
        assert self.summary["uncovered_vms"] == 0

    def test_hero_deferred(self):
        assert self.summary["deferred_vms"] == 1

    def test_hero_drifted(self):
        assert self.summary["drifted_vms"] == 1

    def test_hero_manual(self):
        assert self.summary["manual"] == 2

    def test_hero_orphaned(self):
        assert self.summary["orphaned_tests"] == 1

    def test_hero_math_adds_up(self):
        """pass + fail + manual + uncovered + drifted + deferred must equal total VMs."""
        s = self.summary
        total = s["passed"] + s["failed"] + s["manual"] + s["uncovered_vms"] + s["drifted_vms"] + s["deferred_vms"]
        assert total == s["total_vms"], f"{total} != {s['total_vms']}"

    def test_hero_pipeline_badge_shows_attention(self):
        """Pipeline has failures, so badge should say Attention Required."""
        assert "Attention Required" in self.html

    # ---- TAB 1: TRACEABILITY - STATUS ASSIGNMENT ----

    def test_vm01_pass(self):
        r = self.rows["SYS-REQ-001-VM-01"]
        assert r["status"] == "pass"
        assert r["test_result"] == "passed"
        assert r["scenario_name"] is not None

    def test_vm02_fail(self):
        r = self.rows["SYS-REQ-001-VM-02"]
        assert r["status"] == "fail"
        assert r["test_result"] == "failed"
        assert r["scenario_name"] == "System handles 100 concurrent ICD requests"

    def test_req002_pass(self):
        r = self.rows["SYS-REQ-002-VM-01"]
        assert r["status"] == "pass"
        assert r["test_result"] == "passed"

    def test_req003_vm01_pass(self):
        r = self.rows["SYS-REQ-003-VM-01"]
        assert r["status"] == "pass"
        assert r["method"] == "Demonstration"

    def test_req003_vm02_deferred(self):
        r = self.rows["SYS-REQ-003-VM-02"]
        assert r["status"] == "deferred"
        assert r["test_result"] is None
        assert r["scenario_name"] is None
        assert r["target_release"] == "1.1.0"

    def test_req004_manual_analysis(self):
        r = self.rows["SYS-REQ-004-VM-01"]
        assert r["status"] == "manual"
        assert r["method"] == "Analysis"
        assert r["test_result"] is None
        assert r["scenario_name"] is None

    def test_req005_drifted(self):
        r = self.rows["SYS-REQ-005-VM-01"]
        assert r["status"] == "drifted"
        assert r["test_result"] is None
        assert r["scenario_name"] is None

    def test_req006_manual_inspection(self):
        r = self.rows["SYS-REQ-006-VM-01"]
        assert r["status"] == "manual"
        assert r["method"] == "Inspection"
        assert r["test_result"] is None

    def test_orphaned_tests_present(self):
        orphaned = self.report["orphaned_tests"]
        assert len(orphaned) == 1
        assert "SYS-REQ-099" in orphaned[0].get("orphaned_req_ids", [])

    # ---- TAB 1: NO CROSS-CONTAMINATION ----

    def test_deferred_vm_not_inheriting_sibling_results(self):
        """REQ-003 has 2 VMs. VM-01 passes. VM-02 (deferred) must NOT inherit VM-01's result."""
        vm02 = self.rows["SYS-REQ-003-VM-02"]
        assert vm02["test_result"] is None
        assert vm02["scenario_name"] is None

    def test_drifted_vm_not_inheriting_results(self):
        """REQ-005's VM is drifted. It must NOT show a test result."""
        vm = self.rows["SYS-REQ-005-VM-01"]
        assert vm["test_result"] is None

    def test_fail_vm_gets_correct_scenario_not_sibling(self):
        """REQ-001 VM-02 (fail) must get the load test scenario, not VM-01's scenario."""
        vm02 = self.rows["SYS-REQ-001-VM-02"]
        assert vm02["scenario_name"] == "System handles 100 concurrent ICD requests"
        # Must NOT be any of VM-01's scenarios
        assert vm02["scenario_name"] != "Valid ICD request produces correct response"
        assert vm02["scenario_name"] != "All ICD responses are within latency threshold"

    # ---- TAB 2: SECURITY ----

    def test_sbom_null(self):
        assert self.js_sbom is None

    def test_grype_null(self):
        assert self.js_grype is None

    def test_security_empty_state_in_html(self):
        assert "Cyber Scan Data Not Included" in self.html

    # ---- TAB 3: QUALITY GATES ----

    def test_gate_a_passes_with_deferred(self):
        """Gate A passes because the only uncovered VM is deferred."""
        ga = self.js_trace["gate_a"]
        assert ga["passed"] is True
        assert len(ga["items"]) == 1
        assert ga["items"][0]["verificationMethodId"] == "SYS-REQ-003-VM-02"

    def test_gate_a_item_is_deferred(self):
        item = self.js_trace["gate_a"]["items"][0]
        assert item["deferred"] is True
        assert item["targetRelease"] == "1.1.0"

    def test_gate_b_failed_with_drift(self):
        gb = self.js_trace["gate_b"]
        assert gb["passed"] is False
        assert len(gb["items"]) == 1
        assert gb["items"][0]["verificationMethodId"] == "SYS-REQ-005-VM-01"

    def test_gate_b_has_hash_diff(self):
        item = self.js_trace["gate_b"]["items"][0]
        assert "oldHash" in item and "newHash" in item
        assert item["oldHash"] != item["newHash"]

    def test_gate_c_failed_with_orphan(self):
        gc = self.js_trace["gate_c"]
        assert gc["passed"] is False
        assert len(gc["items"]) == 1
        assert gc["items"][0]["orphanedReqIds"] == ["SYS-REQ-099"]

    def test_gate_c_has_vm_ids(self):
        item = self.js_trace["gate_c"]["items"][0]
        assert "orphanedVmIds" in item
        assert "SYS-REQ-099-VM-01" in item["orphanedVmIds"]

    def test_overall_pipeline_fails(self):
        assert self.js_trace["overall_pass"] is False

    # ---- TAB 3-TAB 1 CONSISTENCY ----

    def test_gate_a_count_matches_uncovered_plus_deferred(self):
        uncov = [r for r in self.report["requirements"] if r["status"] in ("uncovered", "deferred")]
        assert len(self.js_trace["gate_a"]["items"]) == len(uncov)

    def test_gate_b_count_matches_drifted_rows(self):
        drift = [r for r in self.report["requirements"] if r["status"] == "drifted"]
        assert len(self.js_trace["gate_b"]["items"]) == len(drift)

    def test_gate_c_count_matches_orphaned(self):
        assert len(self.js_trace["gate_c"]["items"]) == self.summary["orphaned_tests"]

    # ---- TAB 4: TEST EXECUTION ----

    def test_behave_has_5_features(self):
        assert len(self.js_behave) == 5

    def test_automated_features_are_4(self):
        """Manual/stub features should be filtered out in Tab 4."""
        manual_tags = {"manual", "stub", "auto_generated"}
        automated = []
        for f in self.js_behave:
            tags = [(t if isinstance(t, str) else t.get("name", "")).replace("@", "").lower()
                    for t in f.get("tags", [])]
            if not manual_tags.intersection(tags):
                automated.append(f)
        assert len(automated) == 5  # All 5 features are automated in demo

    def test_fail_scenario_has_error_message(self):
        feat = [f for f in self.js_behave if f["name"] == "Basic ICD Communications"][0]
        scenario = [e for e in feat["elements"] if e["name"] == "System handles 100 concurrent ICD requests"][0]
        failed_steps = [s for s in scenario["steps"] if s.get("result", {}).get("status") == "failed"]
        assert len(failed_steps) == 1
        assert "Expected 100 responses, got 87" in failed_steps[0]["result"]["error_message"]

    def test_skipped_step_present(self):
        """The step after a failure should be skipped."""
        feat = [f for f in self.js_behave if f["name"] == "Basic ICD Communications"][0]
        scenario = [e for e in feat["elements"] if e["name"] == "System handles 100 concurrent ICD requests"][0]
        skipped = [s for s in scenario["steps"] if s.get("result", {}).get("status") == "skipped"]
        assert len(skipped) == 1

    def test_behave_scenarios_have_vm_tags(self):
        """Every automated scenario should have a @VM: tag."""
        for feat in self.js_behave:
            for el in feat.get("elements", []):
                if el.get("keyword") == "Background":
                    continue
                tags = [(t if isinstance(t, str) else t.get("name", "")).replace("@", "")
                        for t in el.get("tags", [])]
                vm_tags = [t for t in tags if t.startswith("VM:")]
                assert vm_tags, f"Scenario '{el['name']}' missing @VM: tag"

    # ---- TAB 5: EXPORT & METADATA ----

    def test_model_version(self):
        assert self.js_reqs["exportMetadata"]["modelVersion"] == "0.3.0"

    def test_project_name(self):
        assert self.js_reqs["exportMetadata"]["projectName"] == "DemoSystem"

    def test_cameo_version(self):
        assert self.js_reqs["exportMetadata"]["cameoVersion"] == "2024x Refresh2"

    def test_model_version_in_html(self):
        assert "0.3.0" in self.html

    def test_project_name_in_html(self):
        assert "DemoSystem" in self.html

    # ---- HTML STRUCTURE ----

    def test_all_6_tabs_present(self):
        assert 'id="panel-traceability"' in self.html
        assert 'id="panel-releases"' in self.html
        assert 'id="panel-security"' in self.html
        assert 'id="panel-gates"' in self.html
        assert 'id="panel-tests"' in self.html
        assert 'id="panel-export"' in self.html

    def test_all_6_data_vars_injected(self):
        assert "const REPORT = " in self.html
        assert "const REQUIREMENTS = " in self.html
        assert "const BEHAVE = " in self.html
        assert "const TRACEABILITY = " in self.html
        assert "const SBOM = " in self.html
        assert "const GRYPE = " in self.html

    def test_xss_protected(self):
        assert "</script><script>" not in self.html

    def test_no_external_resources(self):
        head = re.search(r"<head>(.*?)</head>", self.html, re.DOTALL)
        if head:
            assert "http://" not in head.group(1)
            assert "https://" not in head.group(1)

    # ---- REQUIREMENT DRILL-DOWN DATA ----

    def test_all_requirements_have_matching_report_rows(self):
        for req in self.js_reqs["requirements"]:
            rid = req["requirementId"]
            vm_ids_in_req = {vm["verificationMethodId"] for vm in req["verificationMethods"]}
            vm_ids_in_report = {r["vm_id"] for r in self.report["requirements"] if r["requirement_id"] == rid}
            assert vm_ids_in_req == vm_ids_in_report, f"VM mismatch for {rid}: {vm_ids_in_req} vs {vm_ids_in_report}"

    def test_req001_has_2_vms(self):
        vms = [r for r in self.report["requirements"] if r["requirement_id"] == "SYS-REQ-001"]
        assert len(vms) == 2

    def test_req003_has_2_vms(self):
        vms = [r for r in self.report["requirements"] if r["requirement_id"] == "SYS-REQ-003"]
        assert len(vms) == 2

    def test_descriptions_present_in_requirements(self):
        for req in self.js_reqs["requirements"]:
            assert req.get("description"), f"{req['requirementId']} missing description"

    def test_satisfied_by_present(self):
        req001 = [r for r in self.js_reqs["requirements"] if r["requirementId"] == "SYS-REQ-001"][0]
        assert req001["satisfiedBy"] == ["ComponentA", "ComponentB"]

    def test_traces_to_present(self):
        req003 = [r for r in self.js_reqs["requirements"] if r["requirementId"] == "SYS-REQ-003"][0]
        assert req003["tracesTo"] == ["SYS-REQ-001"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))

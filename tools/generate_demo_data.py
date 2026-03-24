#!/usr/bin/env python3
"""Generate demo data that exercises every dashboard state.

States covered:
  - PASS:      VM covered, Behave test passed
  - FAIL:      VM covered, Behave test failed
  - UNCOVERED: No scenario exists for a VM
  - DRIFTED:   Verification criteria changed since baseline
  - MANUAL:    Analysis / Inspection verification methods
  - ORPHANED:  Scenario references a requirement that doesn't exist

Usage:
    python tools/generate_demo_data.py --output-dir build/demo
    python tools/report_generator.py \
        --requirements build/demo/requirements.json \
        --behave-results build/demo/behave-results.json \
        --traceability-input build/demo/traceability_report.json \
        --output-json build/demo/final_report.json \
        --output-html build/demo/dashboard.html
"""

import json
import os
import sys
from pathlib import Path


def generate(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Requirements (6 requirements, 10 VMs)
    # ------------------------------------------------------------------
    requirements = {
        "exportMetadata": {
            "exportTimestamp": "2026-03-24T10:00:00Z",
            "cameoVersion": "2024x Refresh2",
            "projectName": "DemoSystem",
            "modelVersion": "0.3.0",
        },
        "requirements": [
            {
                # REQ-001: 2 VMs — VM-01 passes, VM-02 FAILS
                "requirementId": "SYS-REQ-001",
                "title": "Basic ICD Communications",
                "description": "The system shall exchange messages with external systems per the ICD.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationMethods": [
                    {
                        "verificationMethodId": "SYS-REQ-001-VM-01",
                        "method": "Test",
                        "criteria": "Verify that a valid IcdRequest produces a valid IcdResponse within 500ms.",
                    },
                    {
                        "verificationMethodId": "SYS-REQ-001-VM-02",
                        "method": "Test",
                        "criteria": "Verify that the system handles 100 concurrent ICD requests without dropping any.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": [],
            },
            {
                # REQ-002: 1 VM — passes
                "requirementId": "SYS-REQ-002",
                "title": "Health Monitoring",
                "description": "The system shall report health status at a configurable interval.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationMethods": [
                    {
                        "verificationMethodId": "SYS-REQ-002-VM-01",
                        "method": "Test",
                        "criteria": "Verify health status messages are emitted at configured interval.",
                    },
                ],
                "satisfiedBy": ["ComponentA"],
                "tracesTo": [],
            },
            {
                # REQ-003: 2 VMs — VM-01 passes, VM-02 is UNCOVERED
                "requirementId": "SYS-REQ-003",
                "title": "Graceful Degradation",
                "description": "The system shall continue operating in degraded mode when a non-critical subsystem fails.",
                "priority": "Medium",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationMethods": [
                    {
                        "verificationMethodId": "SYS-REQ-003-VM-01",
                        "method": "Demonstration",
                        "criteria": "Demonstrate continued operation when logging subsystem is unavailable.",
                    },
                    {
                        "verificationMethodId": "SYS-REQ-003-VM-02",
                        "method": "Test",
                        "criteria": "Verify via log analysis that critical messages are processed during subsystem failure.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": ["SYS-REQ-001"],
            },
            {
                # REQ-004: 1 VM (Analysis) — MANUAL
                "requirementId": "SYS-REQ-004",
                "title": "Thermal Analysis Compliance",
                "description": "The system shall operate within the thermal envelope defined in the environmental spec.",
                "priority": "Critical",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationMethods": [
                    {
                        "verificationMethodId": "SYS-REQ-004-VM-01",
                        "method": "Analysis",
                        "criteria": "Thermal analysis report confirms all components within operating temperature range.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": [],
            },
            {
                # REQ-005: 1 VM — DRIFTED (criteria changed)
                "requirementId": "SYS-REQ-005",
                "title": "Error Handling",
                "description": "The system shall reject malformed ICD messages without crashing.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": "SYS-REQ-001",
                "verificationMethods": [
                    {
                        "verificationMethodId": "SYS-REQ-005-VM-01",
                        "method": "Test",
                        # This criteria was CHANGED from baseline — triggers drift
                        "criteria": "Verify that malformed IcdRequest results in WARN log, IcdResponse with INVALID_REQUEST, and an incident ticket is auto-created.",
                    },
                ],
                "satisfiedBy": ["ComponentA"],
                "tracesTo": ["SYS-REQ-001"],
            },
            {
                # REQ-006: 1 VM (Inspection) — MANUAL
                "requirementId": "SYS-REQ-006",
                "title": "Physical Interface Inspection",
                "description": "All physical connectors shall conform to MIL-DTL-38999 Series III.",
                "priority": "Medium",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationMethods": [
                    {
                        "verificationMethodId": "SYS-REQ-006-VM-01",
                        "method": "Inspection",
                        "criteria": "Visual and dimensional inspection of all connectors against MIL-DTL-38999.",
                    },
                ],
                "satisfiedBy": [],
                "tracesTo": [],
            },
        ],
    }

    # ------------------------------------------------------------------
    # 2. Behave results (real test execution output)
    # ------------------------------------------------------------------
    def step(keyword, name, status="passed", duration=0.001, error=None):
        s = {
            "keyword": keyword,
            "name": name,
            "result": {"status": status, "duration": duration},
        }
        if error:
            s["result"]["error_message"] = error
        return s

    behave_results = [
        # Feature 1: Basic ICD — 2 scenarios for VM-01 (pass), 1 for VM-02 (FAIL)
        {
            "keyword": "Feature",
            "name": "Basic ICD Communications",
            "tags": ["REQ:SYS-REQ-001"],
            "location": "features/automated/sys_req_001_basic_comms.feature:2",
            "status": "failed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "Valid ICD request produces correct response",
                    "tags": ["VM:SYS-REQ-001-VM-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the simulation logs are loaded"),
                        step("Then ", 'the product logs should contain "Received IcdRequest: test-001"'),
                        step("And ", 'the product logs should contain "Sent IcdResponse: status=OK"', duration=0.002),
                        step("And ", "no error entries should appear in the product logs"),
                    ],
                },
                {
                    "keyword": "Scenario",
                    "name": "All ICD responses are within latency threshold",
                    "tags": ["VM:SYS-REQ-001-VM-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the simulation logs are loaded"),
                        step("Then ", "every IcdResponse should occur within 500ms of its IcdRequest", duration=0.003),
                        step("And ", "the average response time should be less than 200ms"),
                    ],
                },
                {
                    # VM-02: FAILS — load test scenario
                    "keyword": "Scenario",
                    "name": "System handles 100 concurrent ICD requests",
                    "tags": ["VM:SYS-REQ-001-VM-02", "VER:Test"],
                    "type": "scenario",
                    "status": "failed",
                    "steps": [
                        step("Given ", "the simulation logs are loaded"),
                        step("When ", "100 concurrent IcdRequests are sent"),
                        step("Then ", "all 100 IcdResponses should be received", status="failed", duration=0.150,
                             error="AssertionError: Expected 100 responses, got 87. 13 requests were dropped under load."),
                        step("And ", "no IcdResponse should have status ERROR", status="skipped"),
                    ],
                },
            ],
        },
        # Feature 2: Health Monitoring — passes
        {
            "keyword": "Feature",
            "name": "Health Monitoring",
            "tags": ["REQ:SYS-REQ-002"],
            "location": "features/automated/sys_req_002_health_monitoring.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "Health status messages are emitted at interval",
                    "tags": ["VM:SYS-REQ-002-VM-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the simulation logs are loaded"),
                        step("Then ", 'the product logs should contain "HealthStatus emitted"'),
                        step("And ", "health messages should appear at most 5 seconds apart", duration=0.002),
                    ],
                },
            ],
        },
        # Feature 3: Graceful Degradation — VM-01 passes (only VM-01 has a scenario)
        {
            "keyword": "Feature",
            "name": "Graceful Degradation",
            "tags": ["REQ:SYS-REQ-003"],
            "location": "features/automated/sys_req_003_graceful_degradation.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "System continues processing when non-critical subsystem fails",
                    "tags": ["VM:SYS-REQ-003-VM-01", "VER:Demonstration"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the simulation logs are loaded"),
                        step("Then ", 'the product logs should contain "Non-critical subsystem unavailable"'),
                        step("And ", 'the product logs should contain "Continuing in degraded mode"'),
                        step("And ", "no crash or panic entries should appear in the product logs"),
                    ],
                },
                # NOTE: No scenario for VM-02 — it is UNCOVERED
            ],
        },
        # Feature 4: Error Handling — has a scenario but VM is DRIFTED
        {
            "keyword": "Feature",
            "name": "Error Message Handling",
            "tags": ["REQ:SYS-REQ-005"],
            "location": "features/automated/sys_req_005_error_handling.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "Malformed messages are rejected with warnings",
                    "tags": ["VM:SYS-REQ-005-VM-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the simulation logs are loaded"),
                        step("Then ", 'the product logs should contain "Malformed message rejected"'),
                        step("And ", "no crash or panic entries should appear"),
                    ],
                },
            ],
        },
        # Feature 5: ORPHANED — references a deleted requirement
        {
            "keyword": "Feature",
            "name": "Legacy Telemetry Validation",
            "tags": ["REQ:SYS-REQ-099"],
            "location": "features/automated/sys_req_099_telemetry.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "Telemetry packets are within expected range",
                    "tags": ["VM:SYS-REQ-099-VM-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the simulation logs are loaded"),
                        step("Then ", "all telemetry values should be within nominal range"),
                    ],
                },
            ],
        },
    ]

    # ------------------------------------------------------------------
    # 3. Traceability report (gate results)
    # ------------------------------------------------------------------
    traceability_report = {
        "timestamp": "2026-03-24T10:05:00Z",
        "requirements_total": 6,
        "features_scanned": 5,
        "vms_total": 8,
        "vms_covered": 6,
        "gate_a": {
            "gate": "A",
            "passed": False,
            "items": [
                {
                    "requirementId": "SYS-REQ-003",
                    "verificationMethodId": "SYS-REQ-003-VM-02",
                    "method": "Test",
                    "title": "Graceful Degradation",
                    "stubGenerated": "bdd/features/automated/sys_req_003_vm_02.feature",
                },
            ],
            "message": "1 uncovered verification criteria found; 1 stub generated.",
        },
        "gate_b": {
            "gate": "B",
            "passed": False,
            "items": [
                {
                    "requirementId": "SYS-REQ-005",
                    "verificationMethodId": "SYS-REQ-005-VM-01",
                    "method": "Test",
                    "title": "Error Handling",
                    "oldHash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
                    "newHash": "f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1",
                    "oldCriteria": "Verify that sending a malformed IcdRequest results in a WARN log and an IcdResponse with status INVALID_REQUEST.",
                    "newCriteria": "Verify that malformed IcdRequest results in WARN log, IcdResponse with INVALID_REQUEST, and an incident ticket is auto-created.",
                    "affectedFeatureFiles": ["features/automated/sys_req_005_error_handling.feature"],
                },
            ],
            "message": "1 drifted verification criteria detected. Scenarios flagged for review.",
        },
        "gate_c": {
            "gate": "C",
            "passed": False,
            "items": [
                {
                    "featureFile": "features/automated/sys_req_099_telemetry.feature",
                    "scenarioName": "Telemetry packets are within expected range",
                    "orphanedReqIds": ["SYS-REQ-099"],
                    "orphanedVmIds": ["SYS-REQ-099-VM-01"],
                },
            ],
            "message": "1 orphaned scenario found referencing deleted requirement SYS-REQ-099.",
        },
        "overall_pass": False,
    }

    # ------------------------------------------------------------------
    # 4. SBOM (CycloneDX from Syft)
    # ------------------------------------------------------------------
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "version": 1,
        "components": [
            {"name": "glibc", "version": "2.35-0ubuntu3.6", "type": "library", "purl": "pkg:deb/ubuntu/glibc@2.35-0ubuntu3.6"},
            {"name": "openssl", "version": "3.0.13", "type": "library", "purl": "pkg:deb/ubuntu/openssl@3.0.13"},
            {"name": "libcurl", "version": "7.88.1", "type": "library", "purl": "pkg:deb/debian/libcurl@7.88.1"},
            {"name": "zlib", "version": "1.2.13", "type": "library", "purl": "pkg:deb/debian/zlib@1.2.13"},
            {"name": "protobuf", "version": "3.21.12", "type": "library", "purl": "pkg:pypi/protobuf@3.21.12"},
            {"name": "grpcio", "version": "1.60.0", "type": "library", "purl": "pkg:pypi/grpcio@1.60.0"},
            {"name": "boost", "version": "1.83.0", "type": "library", "purl": "pkg:conan/boost@1.83.0"},
            {"name": "spdlog", "version": "1.12.0", "type": "library", "purl": "pkg:conan/spdlog@1.12.0"},
            {"name": "nlohmann-json", "version": "3.11.3", "type": "library", "purl": "pkg:conan/nlohmann_json@3.11.3"},
            {"name": "fmt", "version": "10.2.1", "type": "library", "purl": "pkg:conan/fmt@10.2.1"},
            {"name": "yaml-cpp", "version": "0.8.0", "type": "library", "purl": "pkg:conan/yaml-cpp@0.8.0"},
            {"name": "catch2", "version": "3.5.2", "type": "library", "purl": "pkg:conan/catch2@3.5.2"},
        ],
    }

    # ------------------------------------------------------------------
    # 5. Grype vulnerability scan results
    # ------------------------------------------------------------------
    grype = {
        "matches": [
            {
                "vulnerability": {
                    "id": "CVE-2024-5535",
                    "severity": "Critical",
                    "description": "OpenSSL SSL_select_next_proto buffer overread allows remote attackers to cause denial of service via crafted ALPN protocol list.",
                    "fix": {"versions": ["3.0.15"]},
                },
                "artifact": {"name": "openssl", "version": "3.0.13"},
            },
            {
                "vulnerability": {
                    "id": "CVE-2024-2236",
                    "severity": "High",
                    "description": "libcurl SOCKS5 heap buffer overflow when hostname exceeds 255 bytes in non-blocking mode.",
                    "fix": {"versions": ["7.88.2"]},
                },
                "artifact": {"name": "libcurl", "version": "7.88.1"},
            },
            {
                "vulnerability": {
                    "id": "CVE-2023-45853",
                    "severity": "Medium",
                    "description": "MiniZip in zlib through 1.3 has an integer overflow and resultant heap-based buffer overflow in zipOpenNewFileInZip4_64.",
                    "fix": {"versions": ["1.3.1"]},
                },
                "artifact": {"name": "zlib", "version": "1.2.13"},
            },
            {
                "vulnerability": {
                    "id": "CVE-2024-34156",
                    "severity": "Medium",
                    "description": "Stack exhaustion in encoding/gob Decoder.Decode allows a malicious message to crash the server.",
                    "fix": {"versions": []},
                },
                "artifact": {"name": "grpcio", "version": "1.60.0"},
            },
            {
                "vulnerability": {
                    "id": "CVE-2023-50782",
                    "severity": "Low",
                    "description": "Bleichenbacher-style side channel in glibc RSA PKCS#1 v1.5 decryption allows plaintext recovery under specific conditions.",
                    "fix": {"versions": ["2.35-0ubuntu3.8"]},
                },
                "artifact": {"name": "glibc", "version": "2.35-0ubuntu3.6"},
            },
            {
                "vulnerability": {
                    "id": "CVE-2024-0727",
                    "severity": "Low",
                    "description": "Processing maliciously crafted PKCS12 files may cause OpenSSL to crash leading to denial of service.",
                    "fix": {"versions": ["3.0.14"]},
                },
                "artifact": {"name": "openssl", "version": "3.0.13"},
            },
            {
                "vulnerability": {
                    "id": "CVE-2023-52425",
                    "severity": "Negligible",
                    "description": "libexpat through 2.5.0 allows XML Entity Expansion in specific multi-threading configurations.",
                    "fix": {"versions": []},
                },
                "artifact": {"name": "glibc", "version": "2.35-0ubuntu3.6"},
            },
        ],
    }

    # ------------------------------------------------------------------
    # Write files
    # ------------------------------------------------------------------
    def write(name, data):
        path = output_dir / name
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Written: {path}")

    write("requirements.json", requirements)
    write("behave-results.json", behave_results)
    write("traceability_report.json", traceability_report)
    write("sbom.json", sbom)
    write("grype-results.json", grype)

    print()
    print("Demo data states:")
    print("  SYS-REQ-001-VM-01  Test           -> PASS   (2 passing scenarios)")
    print("  SYS-REQ-001-VM-02  Test           -> FAIL   (load test drops 13 requests)")
    print("  SYS-REQ-002-VM-01  Test           -> PASS")
    print("  SYS-REQ-003-VM-01  Demonstration  -> PASS")
    print("  SYS-REQ-003-VM-02  Test           -> UNCOVERED (no scenario written)")
    print("  SYS-REQ-004-VM-01  Analysis       -> MANUAL")
    print("  SYS-REQ-005-VM-01  Test           -> DRIFTED (criteria changed)")
    print("  SYS-REQ-006-VM-01  Inspection     -> MANUAL")
    print("  SYS-REQ-099        (deleted)       -> ORPHANED (test references removed req)")
    print()
    print(f"Now run:\n  python tools/report_generator.py \\")
    print(f"    --requirements {output_dir}/requirements.json \\")
    print(f"    --behave-results {output_dir}/behave-results.json \\")
    print(f"    --traceability-input {output_dir}/traceability_report.json \\")
    print(f"    --sbom-path {output_dir}/sbom.json \\")
    print(f"    --grype-path {output_dir}/grype-results.json \\")
    print(f"    --output-json {output_dir}/final_report.json \\")
    print(f"    --output-html {output_dir}/dashboard.html")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("build/demo"))
    args = parser.parse_args()
    generate(args.output_dir)

#!/usr/bin/env python3
"""Generate demo data that exercises every dashboard state.

States covered:
  - PASS:      VC covered, Behave test passed
  - FAIL:      VC covered, Behave test failed
  - UNCOVERED: No scenario exists for a VC
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
    # 1. Requirements (6 requirements, 10 VCs)
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
                # REQ-001: 2 VCs — VC-01 passes, VC-02 FAILS
                "requirementId": "SYS-REQ-001",
                "title": "Basic ICD Communications",
                "description": "The system shall exchange messages with external systems per the ICD.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-001-VC-01",
                        "method": "Test",
                        "criteria": "Verify that a valid IcdRequest produces a valid IcdResponse within 500ms.",
                    },
                    {
                        "verificationCriteriaId": "SYS-REQ-001-VC-02",
                        "method": "Test",
                        "criteria": "Verify that the system handles 100 concurrent ICD requests without dropping any.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": [],
            },
            {
                # REQ-002: 1 VC — passes
                "requirementId": "SYS-REQ-002",
                "title": "Health Monitoring",
                "description": "The system shall report health status at a configurable interval.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-002-VC-01",
                        "method": "Test",
                        "criteria": "Verify health status messages are emitted at configured interval.",
                    },
                ],
                "satisfiedBy": ["ComponentA"],
                "tracesTo": [],
            },
            {
                # REQ-003: 2 VCs — VC-01 passes, VC-02 is UNCOVERED
                "requirementId": "SYS-REQ-003",
                "title": "Graceful Degradation",
                "description": "The system shall continue operating in degraded mode when a non-critical subsystem fails.",
                "priority": "Medium",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-003-VC-01",
                        "method": "Demonstration",
                        "criteria": "Demonstrate continued operation when logging subsystem is unavailable.",
                    },
                    {
                        "verificationCriteriaId": "SYS-REQ-003-VC-02",
                        "method": "Test",
                        "criteria": "Verify via log analysis that critical messages are processed during subsystem failure.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": ["SYS-REQ-001"],
            },
            {
                # REQ-004: 1 VC (Analysis) — MANUAL
                "requirementId": "SYS-REQ-004",
                "title": "Thermal Analysis Compliance",
                "description": "The system shall operate within the thermal envelope defined in the environmental spec.",
                "priority": "Critical",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-004-VC-01",
                        "method": "Analysis",
                        "criteria": "Thermal analysis report confirms all components within operating temperature range.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": [],
            },
            {
                # REQ-005: 1 VC — DRIFTED (criteria changed)
                "requirementId": "SYS-REQ-005",
                "title": "Error Handling",
                "description": "The system shall reject malformed ICD messages without crashing.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": "SYS-REQ-001",
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-005-VC-01",
                        "method": "Test",
                        # This criteria was CHANGED from baseline — triggers drift
                        "criteria": "Verify that malformed IcdRequest results in WARN log, IcdResponse with INVALID_REQUEST, and an incident ticket is auto-created.",
                    },
                ],
                "satisfiedBy": ["ComponentA"],
                "tracesTo": ["SYS-REQ-001"],
            },
            {
                # REQ-006: 1 VC (Inspection) — MANUAL
                "requirementId": "SYS-REQ-006",
                "title": "Physical Interface Inspection",
                "description": "All physical connectors shall conform to MIL-DTL-38999 Series III.",
                "priority": "Medium",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-006-VC-01",
                        "method": "Inspection",
                        "criteria": "Visual and dimensional inspection of all connectors against MIL-DTL-38999.",
                    },
                ],
                "satisfiedBy": [],
                "tracesTo": [],
            },
            {
                # REQ-007: 2 VCs (Test) — both pass, scoped to 1.1.0
                "requirementId": "SYS-REQ-007",
                "title": "Configuration Management",
                "description": "The system shall support runtime configuration updates without restart.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-007-VC-01",
                        "method": "Test",
                        "criteria": "Verify that configuration changes are applied within 5 seconds without service interruption.",
                    },
                    {
                        "verificationCriteriaId": "SYS-REQ-007-VC-02",
                        "method": "Test",
                        "criteria": "Verify that invalid configuration values are rejected with a descriptive error message.",
                    },
                ],
                "satisfiedBy": ["ComponentA"],
                "tracesTo": [],
            },
            {
                # REQ-008: 1 VC (Test) — pass, scoped to 2.0.0
                "requirementId": "SYS-REQ-008",
                "title": "Startup Self-Test",
                "description": "The system shall perform a self-test on startup and report results.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-008-VC-01",
                        "method": "Test",
                        "criteria": "Verify that self-test completes within 10 seconds and all subsystem checks pass.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": [],
            },
            {
                # REQ-009: 2 VCs (Test + Demonstration) — both scoped to 2.0.0, Test passes, Demo uncovered
                "requirementId": "SYS-REQ-009",
                "title": "Data Logging and Replay",
                "description": "The system shall log all ICD transactions for post-mission replay.",
                "priority": "Medium",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-009-VC-01",
                        "method": "Test",
                        "criteria": "Verify that all ICD transactions are logged with timestamps and can be parsed.",
                    },
                    {
                        "verificationCriteriaId": "SYS-REQ-009-VC-02",
                        "method": "Demonstration",
                        "criteria": "Demonstrate replaying a 10-minute mission log through the simulator.",
                    },
                ],
                "satisfiedBy": ["ComponentA"],
                "tracesTo": ["SYS-REQ-001"],
            },
            {
                # REQ-010: 1 VC (Test) — scoped to 2.0.0, pass
                "requirementId": "SYS-REQ-010",
                "title": "Firmware Update Verification",
                "description": "The system shall verify firmware image integrity before applying updates.",
                "priority": "Critical",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-010-VC-01",
                        "method": "Test",
                        "criteria": "Verify that a corrupted firmware image is rejected and the system continues running the current version.",
                    },
                ],
                "satisfiedBy": ["ComponentB"],
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
        # Feature 1: Basic ICD — 2 scenarios for VC-01 (pass), 1 for VC-02 (FAIL)
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
                    "tags": ["VC:SYS-REQ-001-VC-01", "VER:Test"],
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
                    "tags": ["VC:SYS-REQ-001-VC-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the simulation logs are loaded"),
                        step("Then ", "every IcdResponse should occur within 500ms of its IcdRequest", duration=0.003),
                        step("And ", "the average response time should be less than 200ms"),
                    ],
                },
                {
                    # VC-02: FAILS — load test scenario
                    "keyword": "Scenario",
                    "name": "System handles 100 concurrent ICD requests",
                    "tags": ["VC:SYS-REQ-001-VC-02", "VER:Test"],
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
                    "tags": ["VC:SYS-REQ-002-VC-01", "VER:Test"],
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
        # Feature 3: Graceful Degradation — VC-01 passes (only VC-01 has a scenario)
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
                    "tags": ["VC:SYS-REQ-003-VC-01", "VER:Demonstration"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the simulation logs are loaded"),
                        step("Then ", 'the product logs should contain "Non-critical subsystem unavailable"'),
                        step("And ", 'the product logs should contain "Continuing in degraded mode"'),
                        step("And ", "no crash or panic entries should appear in the product logs"),
                    ],
                },
                # NOTE: No scenario for VC-02 — it is UNCOVERED
            ],
        },
        # Feature 4: Error Handling — has a scenario but VC is DRIFTED
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
                    "tags": ["VC:SYS-REQ-005-VC-01", "VER:Test"],
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
        # Feature 5: Configuration Management — both VCs pass
        {
            "keyword": "Feature",
            "name": "Configuration Management",
            "tags": ["REQ:SYS-REQ-007"],
            "location": "features/automated/sys_req_007_config_mgmt.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "Configuration changes applied without restart",
                    "tags": ["VC:SYS-REQ-007-VC-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the system is running with default configuration"),
                        step("When ", "the configuration file is updated"),
                        step("Then ", "the new configuration should be applied within 5 seconds", duration=0.003),
                        step("And ", "no service interruption should occur"),
                    ],
                },
                {
                    "keyword": "Scenario",
                    "name": "Invalid configuration values are rejected",
                    "tags": ["VC:SYS-REQ-007-VC-02", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the system is running with default configuration"),
                        step("When ", "an invalid configuration value is submitted"),
                        step("Then ", "the system should reject the change with a descriptive error"),
                        step("And ", "the previous configuration should remain active"),
                    ],
                },
            ],
        },
        # Feature 6: Startup Self-Test — passes
        {
            "keyword": "Feature",
            "name": "Startup Self-Test",
            "tags": ["REQ:SYS-REQ-008"],
            "location": "features/automated/sys_req_008_self_test.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "Self-test completes within timeout",
                    "tags": ["VC:SYS-REQ-008-VC-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the system has just started"),
                        step("Then ", 'the logs should contain "Self-test PASSED" within 10 seconds', duration=0.005),
                        step("And ", "all subsystem checks should report OK"),
                    ],
                },
            ],
        },
        # Feature 7: Data Logging — VC-01 passes, VC-02 (Demonstration) not run
        {
            "keyword": "Feature",
            "name": "Data Logging and Replay",
            "tags": ["REQ:SYS-REQ-009"],
            "location": "features/automated/sys_req_009_data_logging.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "All ICD transactions are logged with timestamps",
                    "tags": ["VC:SYS-REQ-009-VC-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the simulation logs are loaded"),
                        step("Then ", "every ICD transaction should have a timestamp"),
                        step("And ", "the log format should be parseable JSON"),
                    ],
                },
            ],
        },
        # Feature 8: Firmware Update — passes
        {
            "keyword": "Feature",
            "name": "Firmware Update Verification",
            "tags": ["REQ:SYS-REQ-010"],
            "location": "features/automated/sys_req_010_firmware.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "Corrupted firmware image is rejected",
                    "tags": ["VC:SYS-REQ-010-VC-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "a corrupted firmware image is available"),
                        step("When ", "the firmware update is initiated"),
                        step("Then ", 'the system should log "Firmware integrity check FAILED"'),
                        step("And ", "the current firmware version should remain active"),
                    ],
                },
            ],
        },
        # Feature 9: ORPHANED — references a deleted requirement
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
                    "tags": ["VC:SYS-REQ-099-VC-01", "VER:Test"],
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
        "requirements_total": 10,
        "features_scanned": 9,
        "vcs_total": 14,
        "vcs_covered": 11,
        "gate_a": {
            "gate": "A",
            "passed": False,
            "items": [
                {
                    "requirementId": "SYS-REQ-003",
                    "verificationCriteriaId": "SYS-REQ-003-VC-02",
                    "method": "Test",
                    "title": "Graceful Degradation",
                    "stubGenerated": "bdd/features/automated/sys_req_003_vc_02.feature",
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
                    "verificationCriteriaId": "SYS-REQ-005-VC-01",
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
                    "orphanedVcIds": ["SYS-REQ-099-VC-01"],
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
    # 6. Release plan
    # ------------------------------------------------------------------
    release_plan = {
        "releases": [
            {
                "version": "1.0.0",
                "targetDate": "2026-06-01",
                "description": "Initial deployment \u2014 core ICD communications, health monitoring, and error handling",
                "scope": [
                    "SYS-REQ-001",
                    "SYS-REQ-002",
                    "SYS-REQ-005",
                ],
            },
            {
                "version": "1.1.0",
                "targetDate": "2026-09-01",
                "description": "Degradation handling, configuration management, and ICD demonstration",
                "scope": [
                    "SYS-REQ-001-VC-02",
                    "SYS-REQ-003",
                    "SYS-REQ-007",
                ],
            },
            {
                "version": "2.0.0",
                "targetDate": "2027-01-01",
                "description": "Full compliance \u2014 thermal analysis, self-test, data logging, firmware, and inspection",
                "scope": [
                    "SYS-REQ-004",
                    "SYS-REQ-006",
                    "SYS-REQ-008",
                    "SYS-REQ-009",
                    "SYS-REQ-010",
                ],
            },
        ],
    }

    # Update traceability to mark out-of-scope VCs as deferred
    # Current release is 1.0.0. Out-of-scope VCs get deferred status.
    # SYS-REQ-009-VC-02 (Demonstration) has no scenario even in its target release.
    traceability_report["gate_a"]["items"] = [
        {
            "requirementId": "SYS-REQ-003",
            "verificationCriteriaId": "SYS-REQ-003-VC-02",
            "method": "Test",
            "title": "Graceful Degradation",
            "deferred": True,
            "targetRelease": "1.1.0",
        },
        {
            "requirementId": "SYS-REQ-007",
            "verificationCriteriaId": "SYS-REQ-007-VC-01",
            "method": "Test",
            "title": "Configuration Management",
            "deferred": True,
            "targetRelease": "1.1.0",
        },
        {
            "requirementId": "SYS-REQ-007",
            "verificationCriteriaId": "SYS-REQ-007-VC-02",
            "method": "Test",
            "title": "Configuration Management",
            "deferred": True,
            "targetRelease": "1.1.0",
        },
        {
            "requirementId": "SYS-REQ-008",
            "verificationCriteriaId": "SYS-REQ-008-VC-01",
            "method": "Test",
            "title": "Startup Self-Test",
            "deferred": True,
            "targetRelease": "2.0.0",
        },
        {
            "requirementId": "SYS-REQ-009",
            "verificationCriteriaId": "SYS-REQ-009-VC-01",
            "method": "Test",
            "title": "Data Logging and Replay",
            "deferred": True,
            "targetRelease": "2.0.0",
        },
        {
            "requirementId": "SYS-REQ-009",
            "verificationCriteriaId": "SYS-REQ-009-VC-02",
            "method": "Demonstration",
            "title": "Data Logging and Replay",
            "deferred": True,
            "targetRelease": "2.0.0",
        },
        {
            "requirementId": "SYS-REQ-010",
            "verificationCriteriaId": "SYS-REQ-010-VC-01",
            "method": "Test",
            "title": "Firmware Update Verification",
            "deferred": True,
            "targetRelease": "2.0.0",
        },
    ]
    traceability_report["gate_a"]["passed"] = True
    traceability_report["gate_a"]["message"] = "All in-scope verification criteria covered; 7 deferred to future releases."

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
    write("release-plan.json", release_plan)

    print()
    print("Demo data states:")
    print("  SYS-REQ-001-VC-01  Test           -> PASS   (2 passing scenarios)")
    print("  SYS-REQ-001-VC-02  Test           -> FAIL   (load test drops 13 requests)")
    print("  SYS-REQ-002-VC-01  Test           -> PASS")
    print("  SYS-REQ-003-VC-01  Demonstration  -> PASS")
    print("  SYS-REQ-003-VC-02  Test           -> UNCOVERED (no scenario written)")
    print("  SYS-REQ-004-VC-01  Analysis       -> MANUAL")
    print("  SYS-REQ-005-VC-01  Test           -> DRIFTED (criteria changed)")
    print("  SYS-REQ-006-VC-01  Inspection     -> MANUAL")
    print("  SYS-REQ-099        (deleted)       -> ORPHANED (test references removed req)")
    print()
    print(f"Now run:\n  python tools/report_generator.py \\")
    print(f"    --requirements {output_dir}/requirements.json \\")
    print(f"    --behave-results {output_dir}/behave-results.json \\")
    print(f"    --traceability-input {output_dir}/traceability_report.json \\")
    print(f"    --sbom-path {output_dir}/sbom.json \\")
    print(f"    --grype-path {output_dir}/grype-results.json \\")
    print(f"    --release-plan {output_dir}/release-plan.json \\")
    print(f"    --output-json {output_dir}/final_report.json \\")
    print(f"    --output-html {output_dir}/dashboard.html")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("build/demo"))
    args = parser.parse_args()
    generate(args.output_dir)

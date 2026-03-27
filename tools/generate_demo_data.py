#!/usr/bin/env python3
"""Generate demo data for a 5-release narrative.

Releases:
  1.0.0 (Released)  — The Clean Baseline
  1.1.0 (Released)  — Building On It
  1.2.0 (Current)   — The Model Changed   (issues: 1 fail, 1 drift, 1 uncovered)
  2.0.0 (Future)    — Planning Ahead       (3 deferred reqs, 1 uncovered)
  2.1.0 (Future)    — Security and Compliance (2 deferred reqs)

11 requirements, 13 VCs, ALL method "Test", NO orphans.

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
    # 1. Requirements (11 requirements, 13 VCs — all method "Test")
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
                # REQ-001: Basic ICD Communications — 2 VCs, both PASS (1.0.0)
                "requirementId": "SYS-REQ-001",
                "title": "Basic ICD Communications",
                "description": "The system shall exchange messages with external systems in accordance with the Interface Control Document (ICD), supporting all defined message types and response codes.",
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
                        "criteria": "Verify correct round-trip ICD message exchange with the hardware simulator across all defined message types.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": [],
            },
            {
                # REQ-002: Health Monitoring — 1 VC, PASS (1.0.0)
                "requirementId": "SYS-REQ-002",
                "title": "Health Monitoring",
                "description": "The system shall report health status to the mission computer at a configurable interval not to exceed 10 seconds.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-002-VC-01",
                        "method": "Test",
                        "criteria": "Verify health status messages are emitted at the configured interval.",
                    },
                ],
                "satisfiedBy": ["ComponentA"],
                "tracesTo": [],
            },
            {
                # REQ-003: Graceful Degradation — 1 VC (1.2.0)
                #   VC-02: UNCOVERED (no scenario written, stub generated)
                "requirementId": "SYS-REQ-003",
                "title": "Graceful Degradation",
                "description": "The system shall continue operating in a degraded mode when a non-critical subsystem fails, maintaining all safety-critical functions.",
                "priority": "Medium",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-003-VC-02",
                        "method": "Test",
                        "criteria": "Verify that critical ICD messages are still processed and responded to during subsystem failure.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": ["SYS-REQ-001"],
            },
            {
                # REQ-004: System Resilience — 1 VC, deferred (2.0.0), has passing scenario
                "requirementId": "SYS-REQ-004",
                "title": "System Resilience",
                "description": "The system shall recover from transient hardware faults within 30 seconds and resume normal operation without operator intervention.",
                "priority": "Critical",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-004-VC-01",
                        "method": "Test",
                        "criteria": "Verify that the system recovers from a simulated transient fault within 30 seconds and resumes processing.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": [],
            },
            {
                # REQ-005: Error Handling — 1 VC, PASS (1.1.0)
                "requirementId": "SYS-REQ-005",
                "title": "Error Handling",
                "description": "The system shall reject malformed ICD messages with a descriptive error response and shall not crash or enter an undefined state.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": "SYS-REQ-001",
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-005-VC-01",
                        "method": "Test",
                        "criteria": "Verify that sending a malformed IcdRequest results in a WARN log and an IcdResponse with status INVALID_REQUEST.",
                    },
                ],
                "satisfiedBy": ["ComponentA"],
                "tracesTo": ["SYS-REQ-001"],
            },
            {
                # REQ-006: Startup Self-Test — 1 VC, deferred (2.0.0), has passing scenario
                "requirementId": "SYS-REQ-006",
                "title": "Startup Self-Test",
                "description": "The system shall perform a comprehensive self-test on startup, verifying all subsystem interfaces, and report pass/fail results to the mission computer.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-006-VC-01",
                        "method": "Test",
                        "criteria": "Verify that self-test completes within 10 seconds and all subsystem checks pass.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": [],
            },
            {
                # REQ-007: Configuration Management — 2 VCs (1.2.0)
                #   VC-01: FAIL (config update took 12.3s, expected <5s)
                #   VC-02: PASS
                "requirementId": "SYS-REQ-007",
                "title": "Configuration Management",
                "description": "The system shall support runtime configuration updates without requiring a restart, applying changes within 5 seconds of receipt.",
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
                # REQ-008: Data Logging — 1 VC, deferred (2.0.0), UNCOVERED (no scenario)
                "requirementId": "SYS-REQ-008",
                "title": "Data Logging",
                "description": "The system shall log all ICD transactions with timestamps for post-mission replay and forensic analysis.",
                "priority": "Medium",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-008-VC-01",
                        "method": "Test",
                        "criteria": "Verify that all ICD transactions are logged with timestamps and can be replayed.",
                    },
                ],
                "satisfiedBy": ["ComponentA"],
                "tracesTo": ["SYS-REQ-001"],
            },
            {
                # REQ-009: Firmware Update — 1 VC, deferred (2.1.0), has passing scenario
                "requirementId": "SYS-REQ-009",
                "title": "Firmware Update",
                "description": "The system shall verify firmware image integrity using cryptographic hash before applying any update, rejecting corrupted images.",
                "priority": "Critical",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-009-VC-01",
                        "method": "Test",
                        "criteria": "Verify that a corrupted firmware image is rejected and the system continues running the current version.",
                    },
                ],
                "satisfiedBy": ["ComponentB"],
                "tracesTo": [],
            },
            {
                # REQ-010: Network Fault Tolerance — 1 VC, deferred (2.1.0), has passing scenario
                "requirementId": "SYS-REQ-010",
                "title": "Network Fault Tolerance",
                "description": "The system shall maintain operation during temporary network interruptions of up to 60 seconds, buffering outbound messages for transmission upon reconnection.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-010-VC-01",
                        "method": "Test",
                        "criteria": "Verify that the system buffers messages during a 60-second network outage and transmits them upon reconnection.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": [],
            },
            {
                # REQ-011: Logging Subsystem Failover — 1 VC (1.2.0)
                #   VC-01: DRIFTED (moved from REQ-003, criteria includes failover language)
                "requirementId": "SYS-REQ-011",
                "title": "Logging Subsystem Failover",
                "description": "The system shall automatically failover to backup logging when the primary logging subsystem is unavailable.",
                "priority": "High",
                "status": "Approved",
                "parentRequirementId": None,
                "verificationCriteria": [
                    {
                        "verificationCriteriaId": "SYS-REQ-011-VC-01",
                        "method": "Test",
                        "criteria": "Verify continued operation when logging subsystem is unavailable, including automatic failover to backup logging.",
                    },
                ],
                "satisfiedBy": ["ComponentA", "ComponentB"],
                "tracesTo": ["SYS-REQ-003"],
            },
        ],
    }

    # ------------------------------------------------------------------
    # 2. Behave results (8 features, no orphans)
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
        # Feature 1: Basic ICD Communications — 2 scenarios, both pass
        {
            "keyword": "Feature",
            "name": "Basic ICD Communications",
            "tags": ["REQ:SYS-REQ-001"],
            "location": "features/automated/sys_req_001_basic_comms.feature:2",
            "status": "passed",
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
                    "name": "Round-trip ICD message exchange with simulator",
                    "tags": ["VC:SYS-REQ-001-VC-02", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the simulation logs are loaded"),
                        step("Then ", 'the product logs should contain "Received IcdRequest: test-001"'),
                        step("And ", 'the product logs should contain "Sent IcdResponse: status=OK"'),
                        step("And ", "all defined message types should be exercised"),
                    ],
                },
            ],
        },
        # Feature 2: Health Monitoring — 1 scenario, passes
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
        # Feature 3: Graceful Degradation — VC-02 is UNCOVERED (no scenarios)
        {
            "keyword": "Feature",
            "name": "Graceful Degradation",
            "tags": ["REQ:SYS-REQ-003"],
            "location": "features/automated/sys_req_003_graceful_degradation.feature:2",
            "status": "passed",
            "elements": [],
        },
        # Feature 3b: Logging Subsystem Failover — VC-01 passes
        {
            "keyword": "Feature",
            "name": "Logging Subsystem Failover",
            "tags": ["REQ:SYS-REQ-011"],
            "location": "features/automated/sys_req_011_logging_failover.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "System continues processing when logging subsystem fails",
                    "tags": ["VC:SYS-REQ-011-VC-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the simulation logs are loaded"),
                        step("Then ", 'the product logs should contain "Non-critical subsystem unavailable"'),
                        step("And ", 'the product logs should contain "Continuing in degraded mode"'),
                        step("And ", "no crash or panic entries should appear in the product logs"),
                    ],
                },
            ],
        },
        # Feature 4: Error Handling — 1 scenario, passes (1.1.0)
        {
            "keyword": "Feature",
            "name": "Error Handling",
            "tags": ["REQ:SYS-REQ-005"],
            "location": "features/automated/sys_req_005_error_handling.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "Malformed messages are rejected without crashing",
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
        # Feature 5: Configuration Management — VC-01 FAILS, VC-02 passes (1.2.0)
        {
            "keyword": "Feature",
            "name": "Configuration Management",
            "tags": ["REQ:SYS-REQ-007"],
            "location": "features/automated/sys_req_007_config_mgmt.feature:2",
            "status": "failed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "Configuration changes applied without restart",
                    "tags": ["VC:SYS-REQ-007-VC-01", "VER:Test"],
                    "type": "scenario",
                    "status": "failed",
                    "steps": [
                        step("Given ", "the system is running with default configuration"),
                        step("When ", "the configuration file is updated"),
                        step("Then ", "the new configuration should be applied within 5 seconds", status="failed", duration=0.008,
                             error="AssertionError: Configuration update took 12.3 seconds, expected < 5 seconds. The hot-reload mechanism is not triggering on file change."),
                        step("And ", "no service interruption should occur", status="skipped"),
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
        # Feature 6: System Resilience — deferred (2.0.0), has passing scenario ahead of schedule
        {
            "keyword": "Feature",
            "name": "System Resilience",
            "tags": ["REQ:SYS-REQ-004"],
            "location": "features/automated/sys_req_004_resilience.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "System recovers from transient fault within timeout",
                    "tags": ["VC:SYS-REQ-004-VC-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the system is operating normally"),
                        step("When ", "a transient hardware fault is injected"),
                        step("Then ", "the system should recover within 30 seconds", duration=0.005),
                        step("And ", "normal processing should resume without operator intervention"),
                    ],
                },
            ],
        },
        # Feature 7: Startup Self-Test — deferred (2.0.0), has passing scenario ahead of schedule
        {
            "keyword": "Feature",
            "name": "Startup Self-Test",
            "tags": ["REQ:SYS-REQ-006"],
            "location": "features/automated/sys_req_006_self_test.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "Self-test completes within timeout",
                    "tags": ["VC:SYS-REQ-006-VC-01", "VER:Test"],
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
        # Feature 8: Firmware Update — deferred (2.1.0), has passing scenario ahead of schedule
        {
            "keyword": "Feature",
            "name": "Firmware Update",
            "tags": ["REQ:SYS-REQ-009"],
            "location": "features/automated/sys_req_009_firmware.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "Corrupted firmware image is rejected",
                    "tags": ["VC:SYS-REQ-009-VC-01", "VER:Test"],
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
        # NOTE: No feature for REQ-008 (Data Logging) — it is deferred AND uncovered
        # Feature 9: ORPHANED — references a deleted requirement (Gate C catches this)
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

    # Feature 9: Network Fault Tolerance — deferred (2.1.0), has passing scenario
    behave_results.append(
        {
            "keyword": "Feature",
            "name": "Network Fault Tolerance",
            "tags": ["REQ:SYS-REQ-010"],
            "location": "features/automated/sys_req_010_network.feature:2",
            "status": "passed",
            "elements": [
                {
                    "keyword": "Scenario",
                    "name": "System buffers messages during network outage",
                    "tags": ["VC:SYS-REQ-010-VC-01", "VER:Test"],
                    "type": "scenario",
                    "status": "passed",
                    "steps": [
                        step("Given ", "the system is connected to the network"),
                        step("When ", "the network connection is interrupted for 60 seconds"),
                        step("Then ", "outbound messages should be buffered"),
                        step("And ", "buffered messages should be transmitted upon reconnection", duration=0.003),
                    ],
                },
            ],
        }
    )

    # ------------------------------------------------------------------
    # 3. Traceability report (gate results)
    # ------------------------------------------------------------------
    traceability_report = {
        "timestamp": "2026-03-24T10:05:00Z",
        "requirements_total": 11,
        "features_scanned": 11,
        "vcs_total": 12,
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
                    "deferred": False,
                    "stubGenerated": "bdd/features/automated/sys_req_003_vc_02.feature",
                },
                {
                    "requirementId": "SYS-REQ-004",
                    "verificationCriteriaId": "SYS-REQ-004-VC-01",
                    "method": "Test",
                    "title": "System Resilience",
                    "deferred": True,
                    "targetRelease": "2.0.0",
                },
                {
                    "requirementId": "SYS-REQ-006",
                    "verificationCriteriaId": "SYS-REQ-006-VC-01",
                    "method": "Test",
                    "title": "Startup Self-Test",
                    "deferred": True,
                    "targetRelease": "2.0.0",
                },
                {
                    "requirementId": "SYS-REQ-008",
                    "verificationCriteriaId": "SYS-REQ-008-VC-01",
                    "method": "Test",
                    "title": "Data Logging",
                    "deferred": True,
                    "targetRelease": "2.0.0",
                },
                {
                    "requirementId": "SYS-REQ-009",
                    "verificationCriteriaId": "SYS-REQ-009-VC-01",
                    "method": "Test",
                    "title": "Firmware Update",
                    "deferred": True,
                    "targetRelease": "2.1.0",
                },
                {
                    "requirementId": "SYS-REQ-010",
                    "verificationCriteriaId": "SYS-REQ-010-VC-01",
                    "method": "Test",
                    "title": "Network Fault Tolerance",
                    "deferred": True,
                    "targetRelease": "2.1.0",
                },
            ],
            "message": "1 uncovered in-scope VC (SYS-REQ-003-VC-02); 5 deferred to future releases.",
        },
        "gate_b": {
            "gate": "B",
            "passed": False,
            "items": [
                {
                    "requirementId": "SYS-REQ-011",
                    "verificationCriteriaId": "SYS-REQ-011-VC-01",
                    "method": "Test",
                    "title": "Logging Subsystem Failover",
                    "oldHash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
                    "newHash": "f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1",
                    "oldCriteria": "Verify continued operation when logging subsystem is unavailable.",
                    "newCriteria": "Verify continued operation when logging subsystem is unavailable, including automatic failover to backup logging.",
                    "affectedFeatureFiles": ["features/automated/sys_req_011_logging_failover.feature"],
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
    # 4. SBOM (CycloneDX from Syft) — kept exactly as-is
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
    # 5. Grype vulnerability scan results — kept exactly as-is (7 CVEs)
    # ------------------------------------------------------------------
    grype = {
        "matches": [
            {
                "vulnerability": {
                    "id": "CVE-2024-5535",
                    "severity": "Critical",
                    "description": "OpenSSL SSL_select_next_proto has an out-of-bounds read when processing a specially formed ALPN protocol list.",
                    "fix": {"versions": ["3.0.15"]},
                },
                "artifact": {"name": "openssl", "version": "3.0.13"},
            },
            {
                "vulnerability": {
                    "id": "CVE-2024-2236",
                    "severity": "High",
                    "description": "libcurl SOCKS5 proxy handshake may write beyond allocated memory when hostname exceeds 255 bytes.",
                    "fix": {"versions": ["7.88.2"]},
                },
                "artifact": {"name": "libcurl", "version": "7.88.1"},
            },
            {
                "vulnerability": {
                    "id": "CVE-2023-45853",
                    "severity": "Medium",
                    "description": "MiniZip in zlib through 1.3 has an arithmetic wraparound in zipOpenNewFileInZip4_64 leading to incorrect memory allocation.",
                    "fix": {"versions": ["1.3.1"]},
                },
                "artifact": {"name": "zlib", "version": "1.2.13"},
            },
            {
                "vulnerability": {
                    "id": "CVE-2024-34156",
                    "severity": "Medium",
                    "description": "Deeply nested encoding/gob messages in Decoder.Decode may cause excessive resource consumption.",
                    "fix": {"versions": []},
                },
                "artifact": {"name": "grpcio", "version": "1.60.0"},
            },
            {
                "vulnerability": {
                    "id": "CVE-2023-50782",
                    "severity": "Low",
                    "description": "Timing side channel in glibc RSA PKCS#1 v1.5 decryption may allow message recovery under specific conditions.",
                    "fix": {"versions": ["2.35-0ubuntu3.8"]},
                },
                "artifact": {"name": "glibc", "version": "2.35-0ubuntu3.6"},
            },
            {
                "vulnerability": {
                    "id": "CVE-2024-0727",
                    "severity": "Low",
                    "description": "Processing certain invalid PKCS12 files may cause OpenSSL to terminate unexpectedly.",
                    "fix": {"versions": ["3.0.14"]},
                },
                "artifact": {"name": "openssl", "version": "3.0.13"},
            },
            {
                "vulnerability": {
                    "id": "CVE-2023-52425",
                    "severity": "Negligible",
                    "description": "libexpat through 2.5.0 may consume excessive resources during XML parsing in specific multi-threading configurations.",
                    "fix": {"versions": []},
                },
                "artifact": {"name": "glibc", "version": "2.35-0ubuntu3.6"},
            },
        ],
    }

    # ------------------------------------------------------------------
    # 6. Release plan (5 releases)
    # ------------------------------------------------------------------
    release_plan = {
        "currentVersion": "1.2.0",
        "releases": [
            {
                "version": "1.0.0",
                "targetDate": "2026-01-15",
                "description": "The Clean Baseline \u2014 core ICD communications and health monitoring",
                "scope": [
                    "SYS-REQ-001",
                    "SYS-REQ-002",
                ],
            },
            {
                "version": "1.1.0",
                "targetDate": "2026-04-01",
                "description": "Building On It \u2014 error handling for malformed messages",
                "scope": [
                    "SYS-REQ-005",
                ],
            },
            {
                "version": "1.2.0",
                "targetDate": "2026-07-01",
                "description": "The Model Changed \u2014 graceful degradation and configuration management",
                "scope": [
                    "SYS-REQ-003",
                    "SYS-REQ-007",
                    "SYS-REQ-011",
                ],
            },
            {
                "version": "2.0.0",
                "targetDate": "2027-01-01",
                "description": "Planning Ahead \u2014 resilience, self-test, and data logging",
                "scope": [
                    "SYS-REQ-004",
                    "SYS-REQ-006",
                    "SYS-REQ-008",
                ],
            },
            {
                "version": "2.1.0",
                "targetDate": "2027-06-01",
                "description": "Security and Compliance \u2014 firmware verification and network fault tolerance",
                "scope": [
                    "SYS-REQ-009",
                    "SYS-REQ-010",
                ],
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
    write("release-plan.json", release_plan)

    print()
    print("Demo data — 5-release narrative:")
    print("  Release 1.0.0 (Released)  — The Clean Baseline")
    print("    SYS-REQ-001-VC-01  Test  PASS")
    print("    SYS-REQ-001-VC-02  Test  PASS")
    print("    SYS-REQ-002-VC-01  Test  PASS")
    print("  Release 1.1.0 (Released)  — Building On It")
    print("    SYS-REQ-005-VC-01  Test  PASS")
    print("  Release 1.2.0 (Current)   — The Model Changed")
    print("    SYS-REQ-003-VC-02  Test  UNCOVERED (no scenario, stub generated)")
    print("    SYS-REQ-007-VC-01  Test  FAIL (config update 12.3s > 5s)")
    print("    SYS-REQ-007-VC-02  Test  PASS")
    print("    SYS-REQ-011-VC-01  Test  DRIFTED (criteria changed: added failover)")
    print("  Release 2.0.0 (Future)    — Planning Ahead")
    print("    SYS-REQ-004-VC-01  Test  deferred (passing scenario ahead of schedule)")
    print("    SYS-REQ-006-VC-01  Test  deferred (passing scenario ahead of schedule)")
    print("    SYS-REQ-008-VC-01  Test  deferred + UNCOVERED (no scenario)")
    print("  Release 2.1.0 (Future)    — Security and Compliance")
    print("    SYS-REQ-009-VC-01  Test  deferred (passing scenario ahead of schedule)")
    print("    SYS-REQ-010-VC-01  Test  deferred (passing scenario ahead of schedule)")
    print()
    print("Gates: A=FAIL, B=FAIL, C=PASS, overall=False")
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

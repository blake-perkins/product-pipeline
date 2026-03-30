#!/usr/bin/env python3
"""Generate sample Cameo model data for GitHub Actions prototype pipeline."""
import json
import os

os.makedirs("build/cameo/requirements", exist_ok=True)
os.makedirs("build/cameo/proto", exist_ok=True)

data = {
    "exportMetadata": {
        "exportTimestamp": "2026-03-10T14:30:00Z",
        "cameoVersion": "2024x Refresh2",
        "projectName": "SampleSystem",
        "modelVersion": "0.2.0",
    },
    "requirements": [
        {
            "requirementId": "SYS-REQ-001",
            "cameoUUID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "name": "Basic ICD Communications",
            "description": "The system shall exchange messages with external systems per the Interface Control Document.",
            "requirementType": "Functional",
            "status": "Approved",
            "parentRequirementId": None,
            "verificationCriteria": [
                {
                    "verificationId": "SYS-REQ-001-VC-01",
                    "verificationMethod": "Test",
                    "verificationDescription": "Verify that a valid IcdRequest message produces a valid IcdResponse within 500ms under nominal load conditions.",
                },
                {
                    "verificationId": "SYS-REQ-001-VC-02",
                    "verificationMethod": "Demonstration",
                    "verificationDescription": "Demonstrate correct round-trip ICD message exchange with the simulator under nominal conditions.",
                },
            ],
        },
        {
            "requirementId": "SYS-REQ-002",
            "cameoUUID": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "name": "Health Monitoring",
            "description": "The system shall report health status at a configurable interval not to exceed 5 seconds.",
            "requirementType": "Functional",
            "status": "Approved",
            "parentRequirementId": None,
            "verificationCriteria": [
                {
                    "verificationId": "SYS-REQ-002-VC-01",
                    "verificationMethod": "Test",
                    "verificationDescription": "Verify that health status messages are emitted at the configured interval with less than 10% jitter.",
                },
            ],
        },
        {
            "requirementId": "SYS-REQ-003",
            "cameoUUID": "c3d4e5f6-a7b8-9012-cdef-123456789012",
            "name": "Graceful Degradation",
            "description": "The system shall continue operating in a degraded mode when a non-critical subsystem fails.",
            "requirementType": "Functional",
            "status": "Approved",
            "parentRequirementId": None,
            "verificationCriteria": [
                {
                    "verificationId": "SYS-REQ-003-VC-01",
                    "verificationMethod": "Demonstration",
                    "verificationDescription": "Demonstrate that the system continues to process critical messages when the logging subsystem is unavailable.",
                },
                {
                    "verificationId": "SYS-REQ-003-VC-02",
                    "verificationMethod": "Test",
                    "verificationDescription": "Verify via log analysis that critical messages continue to be processed when the logging subsystem is disabled.",
                },
            ],
        },
        {
            "requirementId": "SYS-REQ-004",
            "cameoUUID": "d4e5f6a7-b8c9-0123-defa-234567890123",
            "name": "Thermal Analysis Compliance",
            "description": "The system shall operate within the thermal envelope defined in the environmental specification.",
            "requirementType": "Functional",
            "status": "Approved",
            "parentRequirementId": None,
            "verificationCriteria": [
                {
                    "verificationId": "SYS-REQ-004-VC-01",
                    "verificationMethod": "Analysis",
                    "verificationDescription": "Thermal analysis report confirms all components remain within operating temperature range under worst-case power dissipation.",
                },
            ],
        },
        {
            "requirementId": "SYS-REQ-005",
            "cameoUUID": "e5f6a7b8-c9d0-1234-efab-345678901234",
            "name": "Error Handling",
            "description": "The system shall reject malformed ICD messages without crashing or entering an undefined state.",
            "requirementType": "Functional",
            "status": "Approved",
            "parentRequirementId": "SYS-REQ-001",
            "verificationCriteria": [
                {
                    "verificationId": "SYS-REQ-005-VC-01",
                    "verificationMethod": "Test",
                    "verificationDescription": "Verify that sending a malformed IcdRequest results in a WARN log and an IcdResponse with status INVALID_REQUEST.",
                },
            ],
        },
        {
            "requirementId": "SYS-REQ-006",
            "cameoUUID": "f6a7b8c9-d0e1-2345-fabc-456789012345",
            "name": "Physical Interface Inspection",
            "description": "All physical connectors shall conform to MIL-DTL-38999 Series III specifications.",
            "requirementType": "Functional",
            "status": "Approved",
            "parentRequirementId": None,
            "verificationCriteria": [
                {
                    "verificationId": "SYS-REQ-006-VC-01",
                    "verificationMethod": "Inspection",
                    "verificationDescription": "Visual and dimensional inspection of all connectors against MIL-DTL-38999 Series III drawings.",
                },
            ],
        },
    ],
}

with open("build/cameo/requirements/requirements.json", "w") as f:
    json.dump(data, f, indent=2)

vm_count = sum(len(r["verificationCriteria"]) for r in data["requirements"])
print(f"Generated {len(data['requirements'])} sample requirements with {vm_count} verification criteria")

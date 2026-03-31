# Cameo-to-Deployment Pipeline Guide

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [For Systems Engineers: Cameo Export Workflow](#3-for-systems-engineers-cameo-export-workflow)
4. [For Developers: Writing and Managing BDD Tests](#4-for-developers-writing-and-managing-bdd-tests)
5. [Quality Gates](#5-quality-gates)
6. [Pipeline Stages](#6-pipeline-stages)
7. [Data Model Reference](#7-data-model-reference)
8. [Traceability Reports](#8-traceability-reports)
9. [Release Planning](#9-release-planning)
10. [Traceability Dashboard](#10-traceability-dashboard)
11. [Common Scenarios and Troubleshooting](#11-common-scenarios-and-troubleshooting)
12. [Air-Gapped Environment](#12-air-gapped-environment)
13. [Compliance and Audit](#13-compliance-and-audit)

---

## 1. Executive Summary

### What This Pipeline Does

This pipeline enforces **end-to-end traceability** from requirements captured in Cameo Systems Modeler through to tested, deployed software. Every requirement in the model is tracked through verification, testing, and deployment -- with automated quality gates that prevent gaps from reaching production.

### The Problem It Solves

In traditional workflows, requirements live in a modeling tool, tests live in a test framework, and deployment artifacts live in a registry. There is no automated mechanism to ensure:

- Every requirement has a corresponding test
- Test scenarios still match the current requirement text when models change
- Removed requirements don't leave orphaned tests behind
- All verification evidence is linked and auditable

This pipeline closes those gaps automatically.

### How It Works (30-Second Version)

```
Cameo Model ──> JSON Export ──> Versioned Artifact (Repo 1)
                                       │
                                       ▼
                        Product Pipeline (Repo 2)
                                       │
         ┌─────────────────────────────┼──────────────────────────────┐
         │                             │                              │
    Quality Gates              Deploy + Simulate              Security Scan
    (traceability)             (Helm + simulator)             (Syft + Grype)
         │                             │                              │
         │                        Collect Logs                        │
         │                             │                              │
         │                      BDD Log Analysis                      │
         │                      (Behave/Gherkin)                      │
         │                             │                              │
         └─────────────────────────────┼──────────────────────────────┘
                                       │
                              Traceability Report
                              Release Bundle
```

### Key Principles

- **Model is the source of truth.** Requirements and ICD definitions originate in Cameo. The pipeline consumes exports -- it never modifies the model.
- **Traceability is enforced, not optional.** The pipeline will not pass if any verification criteria lacks a test scenario. No exceptions.
- **Tests are passive log analyzers.** BDD scenarios read log files collected after simulation runs. They do not interact with running systems. This makes tests deterministic and reproducible.
- **Clean break versioning.** Model artifacts are semantically versioned. The product pipeline pins to a specific model version, ensuring reproducibility.
- **Collaborative test authoring.** Systems engineers and developers co-author Gherkin specifications. SEs define *what* to verify (the Feature/Scenario language that captures requirement intent and verification criteriaology). Developers implement *how* to verify it (the Python step definitions behind the Given/When/Then lines). Neither role works in isolation.

---

## 2. Architecture Overview

### Two Repositories

| Repository | Purpose | Maintained By |
|---|---|---|
| `cameo-model-pipeline` | Exports from Cameo → validated, versioned artifact (proto files + requirements JSON) published to Nexus | Systems Engineers |
| `product-pipeline` | Consumes model artifact → runs traceability checks → deploys product → runs BDD tests → produces release bundle | Developers + Systems Engineers (Gherkin co-authoring) |

### Dual CI/CD

Both repositories maintain **GitHub Actions** (prototype/development) and **Jenkinsfile** (production) pipelines. All pipeline logic lives in Python scripts and shell scripts -- the CI/CD definitions just call those scripts. This makes the GitHub Actions → Jenkins migration trivial.

### Artifact Flow

```
cameo-model-pipeline                    product-pipeline
────────────────────                    ────────────────

Cameo .mdzip                            versions.properties
    │                                       │
    ▼ (Groovy macro)                        │ (specifies cameo.version)
JSON exports                                │
    │                                       ▼
    ▼ (pipeline)                        Fetch cameo-model-artifacts.zip from Nexus
Validate → Generate .proto                  │
    │                                       ▼
    ▼                                   Unpack: requirements.json + .proto files
Package zip artifact                        │
    │                                       ├──> Traceability Check (Gates A, B, C)
    ▼                                       ├──> Deploy Product + Simulator (Helm)
Publish to Nexus ─────────────────────>     ├──> Collect Logs
                                            ├──> BDD Log Analysis (Behave)
                                            ├──> Security Scan (Syft/Grype)
                                            └──> Package Release Bundle
```

---

## 3. For Systems Engineers: Cameo Export and Test Co-Authoring

### Overview

Your role has two parts:

1. **Model and export.** You maintain the Cameo model and run the export macros. When you export and push, the pipeline handles validation and artifact publishing.

2. **Co-author Gherkin specifications.** When new requirements or verification criteria are added, you work with developers to write the Gherkin Feature and Scenario text. You are the domain expert -- you know what the requirement means and what the verification criteria is intended to prove. The Gherkin language (Given/When/Then) is plain English and does not require programming knowledge.

You do **not** need to write the Python step implementation code behind the Gherkin steps. That is the developer's responsibility. Your role is to ensure the specification language accurately captures the intent of the requirement and the verification criteriaology.

### Step-by-Step Export Process

1. **Open the model** in Cameo Systems Modeler.

2. **Run the Requirements export macro:**
   - Go to **Tools > Macros > ExportRequirements**
   - The macro writes `exports/requirements_export.json`
   - Verify the output looks correct (open the JSON file)

3. **Run the ICD export macro:**
   - Go to **Tools > Macros > ExportICD**
   - The macro writes `exports/icd_export.json`

4. **Bump the VERSION file** according to the versioning policy:

   | What Changed | Bump | Example |
   |---|---|---|
   | Removed a proto field, changed a type, renumbered fields | MAJOR | 1.2.0 → 2.0.0 |
   | New requirement, new VC, new interface, new field (additive) | MINOR | 1.2.0 → 1.3.0 |
   | Typo fix, description edit, criteria text update | PATCH | 1.2.0 → 1.2.1 |

5. **Commit and push:**
   ```bash
   git add exports/ VERSION
   git commit -m "Update model exports: <brief description>"
   git push
   ```

6. **Pipeline runs automatically.** The CI validates your exports, generates proto files, packages a versioned artifact, and publishes it to Nexus.

### Modeling Conventions

#### Requirements

Every requirement in the model must have:

- A **Requirement ID** (tagged value `Id`): pattern `SYS-REQ-001`
- A **Title**: short descriptive name
- A **Description**: full requirement text (the "shall" statement)
- One or more **Verification Criteria**, each with:
  - A **Verification Criteria ID**: scoped format `SYS-REQ-001-VC-01`
  - A **Method**: one of `Analysis`, `Demonstration`, `Inspection`, or `Test` (INCOSE ADIT)
  - **Criteria**: specific, measurable criteria for how this method verifies the requirement

The Groovy macro automatically extracts these fields and structures them into the JSON export.

#### Example: What the Macro Produces

For a requirement "Basic ICD Communications" with two verification criteria:

```json
{
  "requirementId": "SYS-REQ-001",
  "cameoUUID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Basic ICD Communications",
  "description": "The system shall exchange messages with external systems per the ICD.",
  "priority": "High",
  "status": "Approved",
  "parentRequirementId": null,
  "verificationCriteria": [
    {
      "verificationCriteriaId": "SYS-REQ-001-VC-01",
      "method": "Test",
      "criteria": "Verify that a valid IcdRequest produces a valid IcdResponse within 500ms."
    },
    {
      "verificationCriteriaId": "SYS-REQ-001-VC-02",
      "method": "Demonstration",
      "criteria": "Demonstrate correct round-trip ICD message exchange with the simulator."
    }
  ],
  "satisfiedBy": ["ComponentA", "ComponentB"],
  "tracesTo": []
}
```

### What Happens When You Change Things

| Action | Pipeline Effect | Your Role |
|---|---|---|
| Add a new requirement | Gate A fires: a stub test is auto-generated. The stub intentionally fails, signaling that a real test is needed. | Work with the developer to co-author the Gherkin Feature and Scenario text that replaces the stub. You define what the scenario should verify; the developer implements the step code. |
| Add a new VC to an existing requirement | Same as above -- a stub is generated for the new VC. | Same as above -- help write the Gherkin scenario for the new VC. |
| Change verification criteria text | Gate B fires: `@REVIEW_REQUIRED` tag is injected into the affected feature file. Pipeline fails until reviewed. | Review the existing scenario with the developer. Confirm whether the Gherkin text still captures the intent of the updated criteria, or whether the scenario needs to be rewritten. |
| Remove a requirement | Gate C fires: any test scenarios still referencing the removed requirement are flagged as orphans. Pipeline fails until cleaned up. | Confirm the removal with the developer so they can delete the orphaned scenario. |
| Change a description or title (no criteria change) | No gate fires. The change flows through to reports without blocking. | No action needed. |

### Co-Authoring Gherkin Specifications

When a new requirement or VC needs a test, you and the developer sit down together. Here is how the responsibility splits:

**You (Systems Engineer) own:**
- The Feature description (what capability is being verified)
- The Scenario name (what specific aspect is being checked)
- The Given/When/Then phrasing (what conditions, actions, and expected outcomes matter)
- Ensuring the scenario faithfully represents the verification criteria from the model

**The developer owns:**
- The Python step definition code behind each Given/When/Then line
- The log parsing logic, timing assertions, and error checking
- Ensuring the steps actually work against real simulation logs
- Adding new step definitions when existing ones don't cover the need

**Example collaboration:**

The verification criteria says: *"Verify that a valid IcdRequest produces a valid IcdResponse within 500ms under nominal load conditions."*

You write the Gherkin:
```gherkin
@VC:SYS-REQ-001-VC-01 @VER:Test
Scenario: Valid ICD request produces correct response within latency budget
  Given the simulation logs are loaded
  Then the product logs should contain "Received IcdRequest: test-001"
  And the product logs should contain "Sent IcdResponse: status=OK" within 500ms of the request
  And no error entries should appear in the product logs
```

The developer implements the step `within 500ms of the request` by writing Python code that parses JSON log timestamps and computes the delta. You don't need to see or understand that code -- your job is ensuring the scenario *asks the right question*.

**You do not need to know Python.** Gherkin is designed to be readable and writable by non-programmers. If a step you want to express doesn't exist yet, describe what you need in plain English and the developer will implement it.

---

## 4. For Developers: Writing and Managing BDD Tests

### Overview

Every verification criteria (VC) on every requirement must have at least one Gherkin scenario. The pipeline enforces this automatically. When a new VC appears without a scenario, the pipeline generates a failing stub.

**Your responsibilities:**
- **Implement step definitions** (the Python code behind Given/When/Then lines)
- **Co-author Gherkin specifications** with the systems engineer. The SE defines the verification intent; you ensure it's implementable and wire it to real assertions against simulation logs.
- **Maintain step libraries** so that SEs can compose new scenarios from existing steps whenever possible

When replacing a stub, work with the SE who wrote the requirement. They will help you write the Gherkin text that accurately captures the verification criteria. You then implement the step code to make it pass.

### Understanding the Test Execution Model

BDD tests in this pipeline are **pure log analyzers**. They do not interact with the product or simulator in any way.

```
Pipeline Script (run_simulations.sh)         Behave (BDD)
────────────────────────────────────         ─────────────
1. Deploy product via Helm
2. Deploy simulator via Helm
3. Run simulations
4. Wait for completion
5. Collect logs → build/logs/               Reads build/logs/ only
6. Tear down simulator                      No network calls
7. Tear down product                        No kubectl
                                            No container interaction
                                            Pure file I/O assertions
```

This separation means:
- Tests are deterministic (same logs → same results)
- Tests can be re-run locally without a cluster
- Tests can be debugged by inspecting log files directly

### Tag Conventions

Tags link Gherkin scenarios to requirements and verification criteria.

```gherkin
@REQ:SYS-REQ-001                              ← Feature level: which requirement
Feature: Basic ICD Communications
  ...

  @VC:SYS-REQ-001-VC-01 @VER:Test             ← Scenario level: which VC
  Scenario: Valid ICD request produces response
    ...

  @VC:SYS-REQ-001-VC-02 @VER:Demonstration    ← Different VC, same requirement
  Scenario: Demonstrate round-trip exchange
    ...
```

**Rules:**
- `@REQ:<id>` goes on the **Feature** line. All scenarios in the file inherit it.
- `@VC:<id>` goes on the **Scenario** line. Each scenario declares which VC it covers.
- `@VER:<method>` is optional but recommended for readability. It indicates the INCOSE verification criteria (Test, Demonstration, Analysis, Inspection).
- A scenario can have multiple `@REQ:` tags if it covers multiple requirements.
- A VC can be covered by multiple scenarios (many-to-many relationship).
- A VC is considered "covered" if **at least one** scenario references its `@VC:` tag.

### File Organization

```
bdd/features/
├── automated/                      ← Test and Demonstration scenarios (run by Behave)
│   ├── sys_req_001_basic_comms.feature
│   ├── sys_req_002_health_monitoring.feature
│   └── ...
├── non_test/                       ← Analysis and Inspection scenarios (not run by Behave)
│   ├── analysis/
│   │   └── sys_req_004_thermal.feature
│   ├── inspection/
│   │   └── sys_req_006_connectors.feature
│   └── demonstration/
├── steps/
│   ├── common_steps.py             ← Shared step definitions
│   └── log_analysis_steps.py       ← Log file assertion steps
└── environment.py                  ← Loads log files into context at startup
```

- **`automated/`** contains scenarios with verification criteria `Test` or `Demonstration`. These are executed by Behave in the pipeline.
- **`non_test/`** contains scenarios with verification criteria `Analysis` or `Inspection`. These are tagged `@manual` and tracked for traceability but not executed. They represent verification that happens outside the pipeline (e.g., a thermal analysis report, a physical inspection).

### Writing a New Scenario

When the pipeline generates a stub for an uncovered VC, you'll see a file like this:

```gherkin
@REQ:SYS-REQ-007 @STUB @AUTO_GENERATED
Feature: SYS-REQ-007-VC-01 - Data Logging (Test)
  The system shall log all inbound messages to persistent storage.

  Verification Criteria: Test
  Verification Criteria: Verify that every inbound ICD message appears in the log
  within 1 second of receipt.

  @VC:SYS-REQ-007-VC-01
  Scenario: Verify SYS-REQ-007-VC-01 - Data Logging
    Given the system is configured for test verification of "SYS-REQ-007"
    When the test verification is performed
    Then it should fail because it is not yet implemented
```

**To replace the stub:**

1. **Meet with the systems engineer** who owns the requirement. Review the verification criteria together. The criteria text is included in the stub's Feature description.

2. **Co-author the Gherkin specification.** The SE drafts the Feature description and Scenario text in plain English. You advise on what's implementable given the available log data and existing step definitions. Together, produce something like:

   ```gherkin
   @REQ:SYS-REQ-007
   Feature: Data Logging
     Verify that the system logs all inbound messages to persistent storage.

     @VC:SYS-REQ-007-VC-01 @VER:Test
     Scenario: All inbound messages appear in logs
       Given the simulation logs are loaded
       Then the product logs should contain "Received IcdRequest: test-001"
       And every inbound message should appear in the log within 1 second of receipt
   ```

   The SE ensures this captures the *intent* of the verification criteria. You ensure each line maps to an implementable assertion.

3. Remove `@STUB` and `@AUTO_GENERATED` from the tags.

4. **Implement any new step definitions** needed. If the SE wrote a Then line that doesn't match an existing step, add it to `bdd/features/steps/log_analysis_steps.py` or `common_steps.py`. Share the list of available steps with the SE so they can reuse existing ones in future scenarios.

5. Test locally:
   ```bash
   cd bdd
   LOG_DIR=../build/logs python -m behave features/automated/sys_req_007_data_logging.feature
   ```

6. Commit and push.

### Writing Steps for Log Analysis

All step implementations read from `context.product_logs` and `context.simulator_logs`, which are populated by `environment.py` at startup from `build/logs/`.

**Available step definitions** (in `common_steps.py` and `log_analysis_steps.py`):

| Step | What It Does |
|---|---|
| `Given the simulation logs are loaded` | Verifies logs were loaded and are non-empty |
| `Then the product logs should contain "{text}"` | Searches all product log files for the text |
| `Then the product logs should contain "{text}" within {N}ms of the request` | Verifies timing between correlated log entries |
| `Then the simulator logs should confirm "{text}"` | Searches simulator logs |
| `Then no error entries should appear in the product logs` | Checks for ERROR/FATAL/PANIC entries |
| `Then no ERROR or PANIC entries should appear in the product logs` | Same as above |
| `Then no crash or panic entries should appear in the product logs` | Checks for PANIC/crash entries |
| `Then the product should not have restarted during the simulation` | Checks restart count in metadata |
| `Then every IcdResponse should occur within {N}ms of its corresponding IcdRequest` | Pairs request/response by ID, checks timing |
| `Then the average response time should be less than {N}ms` | Computes average from paired entries |

If you need a step that doesn't exist, add it to the appropriate steps file. Log entries are expected to be JSON-structured (one JSON object per line).

### Manual Verification Criteria (Analysis / Inspection)

For requirements verified by Analysis or Inspection, the pipeline does not run the scenario. Instead, the feature file serves as a **traceability placeholder**:

```gherkin
@REQ:SYS-REQ-004 @manual
Feature: Thermal Analysis Compliance
  The system shall operate within the thermal envelope.

  @VC:SYS-REQ-004-VC-01
  Scenario: Thermal analysis confirms operating range
    Given verification evidence is documented
    Then the analysis report is attached to the verification record
```

The `@manual` tag tells Behave to skip this scenario during execution. It still appears in the traceability matrix as "manual -- pending evidence" or "manual -- evidence provided."

---

## 5. Quality Gates

The pipeline enforces three quality gates that run before any tests execute. All three must pass for the pipeline to succeed.

### Gate A: Uncovered Verification Criteria

**What it checks:** Every verification criteria (VC) in `requirements.json` has at least one Gherkin scenario with a matching `@VC:<id>` tag.

**When it fires:** A new requirement or VC is added to the model without a corresponding test scenario.

**What it does:**
1. Generates a stub `.feature` file for each uncovered VC
2. The stub contains a `Then it should fail because it is not yet implemented` step that raises `NotImplementedError`
3. Reports the uncovered VCs in the traceability output

**Pipeline behavior:** Configurable via `--fail-on-uncovered` flag. When enabled, the pipeline fails. When disabled (current CI default), the pipeline warns but continues -- the stub will cause BDD to fail later.

**Developer action:**
1. Find the generated stub in `bdd/features/automated/` or `bdd/features/non_test/`
2. Replace it with a real scenario (see [Writing a New Scenario](#writing-a-new-scenario))
3. Commit and push

### Gate B: Verification Criteria Drift

**What it checks:** The SHA-256 hash of each VC's `criteria` text matches the hash stored in `.traceability-baseline.json`.

**When it fires:** A systems engineer updates the verification criteria text for an existing VC in the Cameo model, but the existing Gherkin scenario has not been reviewed against the new criteria.

**What it does:**
1. Identifies which VCs have changed criteria
2. Injects a `@REVIEW_REQUIRED` tag into the affected feature file(s)
3. Fails the pipeline with a clear message listing drifted VMs

**Action (developer + SE together):**
1. Open the affected feature file(s) -- look for the `@REVIEW_REQUIRED` tag
2. Compare the current scenario steps against the updated criteria in `requirements.json`
3. Review together: does the existing Gherkin still capture the SE's intent? If the criteria change is substantive, co-author updated scenario text.
4. Remove the `@REVIEW_REQUIRED` tag
5. Update the baseline:
   ```bash
   python tools/traceability_checker.py \
     --requirements build/cameo/requirements/requirements.json \
     --features-dir bdd/features \
     --stubs-output-dir bdd/features/automated \
     --non-test-output-dir bdd/features/non_test \
     --report-output /dev/null \
     --update-baseline
   ```
6. Commit the updated baseline file (`.traceability-baseline.json`) and feature file(s)
7. Push

### Gate C: Orphaned Scenarios

**What it checks:** Every `@REQ:<id>` and `@VC:<id>` tag in the feature files references a requirement or VC that still exists in `requirements.json`.

**When it fires:** A requirement or VC is removed from the Cameo model, but Gherkin scenarios still reference it.

**What it does:**
1. Lists all orphaned requirement IDs and VC IDs
2. Lists which feature files contain the orphaned references
3. Fails the pipeline

**Developer action:**
1. Open the listed feature file(s)
2. Either delete the scenario (if the requirement is truly removed) or reassign it to a different requirement/VC if the ID was renamed
3. Commit and push

### Gate Summary

| Gate | Trigger | Pipeline Effect | Developer Action |
|---|---|---|---|
| **A** (Uncovered) | New VC without a scenario | Generates stub, warns or fails | Write a real scenario |
| **B** (Drift) | VC criteria text changed | Injects `@REVIEW_REQUIRED`, fails | Review scenario, update if needed, update baseline |
| **C** (Orphaned) | VC/requirement removed from model | Fails | Delete or reassign orphaned scenarios |

---

## 6. Pipeline Stages

### Repo 1: Cameo Model Pipeline

| Stage | What Runs | Fails When |
|---|---|---|
| Read Version | Reads `VERSION` file, validates semver format | VERSION is missing or malformed |
| Validate Exports Exist | Checks that `requirements_export.json` and `icd_export.json` exist | Export files are missing (SE forgot to run macros) |
| Schema Validation | `validate_exports.py` -- JSON Schema + business logic checks | Schema violations, duplicate IDs, empty criteria, invalid parent refs |
| Generate Proto Files | `generate_protos.py` -- Jinja2 templates → `.proto` files | Template errors |
| Validate Proto Files | `protoc` compiles each `.proto` to verify syntax | Proto syntax errors |
| Package Artifact | `package_artifact.py` -- assembles versioned zip with manifest | File errors |
| Publish to Nexus | `publish_to_nexus.sh` -- uploads zip to Nexus raw repository | Nexus unreachable, version already exists |
| Tag Release | Creates Git tag `v{VERSION}` (main branch only) | Tag already exists |

### Repo 2: Product Pipeline

| Stage | What Runs | Fails When |
|---|---|---|
| Fetch Cameo Model | Downloads and unpacks the versioned zip from Nexus | Version not found in Nexus |
| Traceability Check | `traceability_checker.py` -- runs Gates A, B, C | Uncovered VCs (if `--fail-on-uncovered`), drift, or orphans |
| Deploy + Simulate | `run_simulations.sh` -- Helm install product + simulator, run simulations, collect logs, tear down | Deployment fails, simulations time out |
| BDD Log Analysis | `behave` -- runs Gherkin scenarios against collected logs | Any scenario fails |
| Traceability Report | `report_generator.py` -- merges requirements + test results → HTML/JSON | Never (runs `if: always()`) |
| Requirements Document | `generate_req_doc.py` -- formats requirements as HTML | Never (runs `if: always()`) |
| Security Scan | `scan.sh` -- Syft (SBOM) + Grype (CVE scan) | CVE severity exceeds threshold |
| Package Release | Assembles final release bundle (Helm chart + docs + reports) | File errors |

---

## 7. Data Model Reference

### Requirements JSON Schema

Each requirement in `requirements.json` has the following structure:

| Field | Type | Required | Description |
|---|---|---|---|
| `requirementId` | string | Yes | Human-readable ID. Pattern: `SYS-REQ-001` |
| `cameoUUID` | string | Yes | Cameo internal UUID |
| `title` | string | Yes | Short requirement title |
| `description` | string | Yes | Full requirement text ("shall" statement) |
| `priority` | enum | No | `Critical`, `High`, `Medium`, `Low` |
| `status` | string | No | Requirement status (e.g., `Approved`, `Draft`) |
| `parentRequirementId` | string/null | No | Parent requirement ID for hierarchy |
| `verificationCriteria` | array | Yes | One or more verification criteria (see below) |
| `satisfiedBy` | string[] | No | Model elements that satisfy this requirement |
| `tracesTo` | string[] | No | Related requirement IDs |

### Verification Criteria Schema

Each item in the `verificationCriteria` array:

| Field | Type | Required | Description |
|---|---|---|---|
| `verificationCriteriaId` | string | Yes | Scoped ID. Pattern: `SYS-REQ-001-VC-01` |
| `method` | enum | Yes | `Analysis`, `Demonstration`, `Inspection`, or `Test` |
| `criteria` | string | Yes | Specific, measurable verification criteria |

### Verification Criteria Types (INCOSE ADIT)

| Method | Automated? | Feature Location | Pipeline Behavior |
|---|---|---|---|
| **Test** | Yes | `bdd/features/automated/` | Executed by Behave |
| **Demonstration** | Yes | `bdd/features/automated/` | Executed by Behave |
| **Analysis** | No | `bdd/features/non_test/analysis/` | Tagged `@manual`, skipped by Behave, tracked in traceability matrix |
| **Inspection** | No | `bdd/features/non_test/inspection/` | Tagged `@manual`, skipped by Behave, tracked in traceability matrix |

### Traceability Baseline (`.traceability-baseline.json`)

This file is committed to Git. It stores SHA-256 hashes of each VC's criteria text for drift detection.

```json
{
  "SYS-REQ-001-VC-01": {
    "criteria_hash": "a1b2c3d4e5f6..."
  },
  "SYS-REQ-001-VC-02": {
    "criteria_hash": "b2c3d4e5f6a7..."
  }
}
```

When a developer runs `--update-baseline`, this file is regenerated from the current `requirements.json`. The Git diff shows exactly when criteria changes were acknowledged.

---

## 8. Traceability Reports

The pipeline produces two report types, both published as build artifacts.

### Deployment Pipeline Report (HTML Dashboard)

Generated by `report_generator.py`. The output is a self-contained 7-tab interactive dashboard (`MBSE_Traceability_Dashboard.html`). In the Traceability Matrix tab, it shows one row per verification criteria:

| Column | Description |
|---|---|
| Requirement ID | The requirement this VC belongs to |
| VC ID | The specific verification criteria ID |
| Title | Requirement title |
| Method | ADIT verification criteria |
| Criteria | Verification criteria text |
| Status | Covered / Uncovered / Drifted / Orphaned |
| Test Result | Pass / Fail / Skipped / Not Run |
| Feature File | Link to the Gherkin feature file |
| Scenario | Name of the covering scenario |

Color coding:
- **Green**: Covered and passing
- **Red**: Uncovered or failing
- **Yellow**: Drifted (criteria changed, review required)
- **Gray**: Manual verification criteria (Analysis/Inspection)

### Requirements Document (HTML)

Generated by `generate_req_doc.py`. Formatted requirements document with:
- Requirement hierarchy (parent/child nesting)
- All verification criteria per requirement in a sub-table
- Priority color coding
- Summary statistics (by priority, status, verification criteria)
- Table of contents with anchor links

---

## 9. Release Planning

### Overview

The pipeline supports **incremental requirement delivery** across multiple releases. A `release-plan.json` file maps requirements and verification criteria to specific release versions. The pipeline only enforces quality gates on VCs that are **in scope** for the current release.

### Release Plan File

Create `release-plan.json` in the repository root:

```json
{
  "releases": [
    {
      "version": "1.0.0",
      "targetDate": "2026-06-01",
      "description": "Initial deployment — core ICD and health monitoring",
      "scope": [
        "SYS-REQ-001",
        "SYS-REQ-002"
      ]
    },
    {
      "version": "1.2.0",
      "targetDate": "2026-09-01",
      "description": "Degradation handling and configuration management",
      "scope": [
        "SYS-REQ-003",
        "SYS-REQ-007"
      ]
    }
  ]
}
```

**Scope supports both levels:**
- A **requirement ID** (e.g., `SYS-REQ-001`) means **all its VCs** are in scope for that release.
- A **VC ID** (e.g., `SYS-REQ-001-VC-02`) means **only that specific VC**.

### How Scope Is Resolved

Scope is **cumulative** — release 1.1.0 includes everything in 1.0.0 plus its own scope. The pipeline reads the current version from the `VERSION` file (or `--release` CLI override) and computes the cumulative in-scope VCs.

### Deferred VCs

VCs that are **not in scope** for the current release appear as **deferred** in the dashboard. They:
- Do NOT fail Gate A (even with `--fail-on-uncovered`)
- Show a "deferred" badge with the target release version
- Are excluded from coverage percentage calculations
- Appear in the Release Progress dashboard tab

### Release Filtering in the Dashboard

The dashboard includes a **global release filter** (dropdown in the hero header). Selecting a specific release filters every tab through a centralized `buildSnapshot()` architecture. Scope is cumulative -- selecting release 1.1.0 shows all VCs from 1.0.0 and 1.1.0 combined. "All Releases" shows everything regardless of release boundaries. Released versions display all gates as passed, no orphans, no vulnerabilities, and a shipped confirmation in the Executive Summary.

### CLI Flags

```bash
# Traceability checker with release plan
python tools/traceability_checker.py \
  --requirements build/cameo/requirements/requirements.json \
  --features-dir bdd/features \
  --stubs-output-dir bdd/features/automated \
  --non-test-output-dir bdd/features/non_test \
  --report-output build/reports/traceability/traceability_report.json \
  --release-plan release-plan.json \
  --release 1.0.0  # optional: override VERSION file

# Report generator with release plan
python tools/report_generator.py \
  --requirements build/cameo/requirements/requirements.json \
  --behave-results build/reports/bdd/behave-results.json \
  --traceability-input build/reports/traceability/traceability_report.json \
  --release-plan release-plan.json \
  --output-json build/reports/traceability/final_report.json \
  --output-html build/reports/traceability/MBSE_Traceability_Dashboard.html
```

### Full Release Management Guide

For detailed workflows including shipping a release, advancing the current version, moving VCs between releases, what-if analysis, and common scenarios, see [docs/release-management.md](release-management.md).

---

## 10. Traceability Dashboard

The pipeline produces a **self-contained HTML dashboard** (`MBSE_Traceability_Dashboard.html`) titled "Deployment Pipeline Report" that opens directly in any browser -- no server, no installation, no network required. The HTML file is fully air-gapped with zero external dependencies, includes cache-busting meta tags, and applies XSS protection via `<\/script>` escaping. Print support is built in via `@media print` styles. A **dark mode toggle** (Light / Dark button) allows switching between light and dark themes. For DemoSystem projects, a demo data banner appears at the bottom of the page.

### Hero Header

A persistent header appears above all tabs with at-a-glance project health:

- **Release Scope** card -- shows the current release name, description, target date, VC count, and a **readiness ring** indicating the percentage of passed VCs. Clicking navigates to the Release Progress tab.
- **Test Results** card -- pass/fail counts with a pass-rate bar and a list of failed VCs. Clicking navigates to the Test Execution tab.
- **Blockers** card -- total blocker count with a breakdown by category (uses amber `--attention` color). Clicking navigates to the Quality Gates tab.
- **Full breakdown bar** -- proportional status bar showing all VC statuses with a color legend.
- **Pipeline badge** -- "Pipeline Pass" or "Attention Required" indicator (amber `--attention` color, not red).

A **global release filter** dropdown sits in the hero header. Selecting a specific release filters every tab through a centralized `buildSnapshot()` architecture. Scope is cumulative -- selecting 1.1.0 includes VCs from 1.0.0 and 1.1.0 combined. "All Releases" shows everything.

### Dashboard Tabs

The dashboard has seven tabs, listed here in display order.

**1. Executive Summary.** High-level readiness view. Shows a compact release-progress view, a list of top issues (clickable -- navigates to Traceability), and a cyber-risk summary. The readiness ring lives in the Release Scope hero card above the tabs, not as a standalone element in the Executive Summary. For released versions the readiness ring is replaced by a shipped confirmation with a checkmark.

**2. Traceability Matrix.** Accordion drill-down: Requirement -> VCs -> Scenarios with full step text. Filter by status, criteria type, or free-text search. Each requirement row includes a mini coverage bar. Drifted verification criteria display a word-level diff highlighting what changed. Each status includes an action hint explaining what to do next.

**3. Quality Gates.** Three gate cards:
- Gate A -- Coverage (are all in-scope VCs tested?)
- Gate B -- Drift Detection (has any verification criteria text changed since the baseline?)
- Gate C -- Orphan Detection (are there test scenarios referencing requirements or VCs that no longer exist?)

Each card shows pass/fail status and a list of affected items. Items are clickable and navigate to the Traceability tab.

**4. Release Progress.** One card per release showing a progress bar and a VC list. VCs are clickable and navigate to Traceability. Releases display RELEASED or CURRENT badges. Scope is cumulative -- later releases include all VCs from earlier ones.

**5. Test Execution.** Behave test results organized by feature, then scenario, then step. Steps display Given/When/Then keyword highlighting, duration, and error messages for failures. Filter by pass/fail or free-text search. Deferred and stub features are filtered out of this tab so only real test results are shown.

**6. Cyber.** SBOM component inventory from Syft and a vulnerability table from Grype. Includes severity breakdown, policy compliance banner, fix availability indicators, CVE filtering, and CSV export. Shows a graceful empty state when no SBOM or Grype data is available.

**7. Export and Info.** Print the dashboard, download the backing JSON, view pipeline metadata, consult the report legend, or browse the MBSE glossary.

### Cross-Tab Navigation

Clicking issues in the Quality Gates, Executive Summary, or Release Progress tabs navigates to the Traceability Matrix tab and highlights the relevant item with a yellow flash. This keeps the Traceability tab as the single source of detail while letting summary tabs serve as entry points.

### Floating Legend

A floating "?" button is available on every tab. It opens a legend overlay with status badge definitions and a glossary of pipeline terms.

### VC Status Reference

| Status | Badge | Meaning |
|--------|-------|---------|
| Pass | Blue | VC has at least one Gherkin scenario and all tests passed |
| Fail | Red | VC has scenarios but one or more tests failed |
| Uncovered | Orange | No scenario exists for this VC (in-scope) |
| Drifted | Yellow | Verification criteria text changed since baseline |
| Deferred | Gray | VC planned for a future release (out of scope) |
| Manual | Dark gray | Analysis or Inspection method -- requires manual review |
| Orphaned | Teal | Scenario references a requirement/VC that no longer exists |

### Demo Data Generator

Generate sample data exercising all dashboard states:

```bash
python tools/generate_demo_data.py --output-dir build/demo

python tools/report_generator.py \
  --requirements build/demo/requirements.json \
  --behave-results build/demo/behave-results.json \
  --traceability-input build/demo/traceability_report.json \
  --sbom-path build/demo/sbom.json \
  --grype-path build/demo/grype-results.json \
  --release-plan release-plan.json \
  --output-json build/demo/final_report.json \
  --output-html build/demo/Deployment_Pipeline_Report.html
```

---

## 11. Common Scenarios and Troubleshooting

### Scenario: A new requirement is added to the Cameo model

**Who acts:** SE exports and co-authors Gherkin, Developer implements steps.

1. SE runs the export macro and pushes.
2. Pipeline runs. Gate A detects the uncovered VC(s). A stub is generated.
   - If the VC is scoped to a future release, the stub includes `@DEFERRED` at the feature and scenario level. The dashboard shows it as "deferred" rather than "failed."
3. If `--fail-on-uncovered` is enabled, the pipeline fails at the traceability check.
4. If not, the pipeline continues but Behave fails on the stub's `NotImplementedError` (unless deferred).
5. SE and developer meet. SE explains the requirement intent and verification criteriaology. Together they co-author the Gherkin Feature and Scenario text.
6. Developer implements any new step definitions needed for the scenario.
7. Developer commits and pushes. Pipeline passes.

### Scenario: Verification criteria text is updated

**Who acts:** SE exports, SE and Developer review together.

1. SE updates the criteria in Cameo, runs the export macro, and pushes.
2. Pipeline runs. Gate B detects the criteria hash mismatch.
3. `@REVIEW_REQUIRED` is injected into the affected feature file. Pipeline fails.
4. SE and developer review the affected scenario together. SE explains what changed in the criteria and why.
5. Together they determine if the existing Gherkin still captures the intent. If not, they co-author updated scenario text.
6. Developer updates step implementations if the assertions changed.
7. Developer removes `@REVIEW_REQUIRED`, runs `--update-baseline` to refresh hashes.
8. Developer commits the updated feature file and baseline. Pipeline passes.

### Scenario: A new requirement is planned for a future release

**Who acts:** SE adds the requirement, PM/SE updates the release plan.

A deferred requirement is one that exists in the model but is not yet in scope for the current release. The pipeline tracks it without enforcing it.

**Step 1: Add the requirement to `requirements.json`**

Add the requirement with its verification criteria, just like any other requirement:

```json
{
  "requirementId": "SYS-REQ-012",
  "name": "Diagnostic Port Access",
  "description": "The system shall provide a secure diagnostic port...",
  "requirementType": "Functional",
  "status": "Approved",
  "parentRequirementId": null,
  "verificationCriteria": [
    {
      "verificationId": "SYS-REQ-012-VC-01",
      "verificationMethod": "Test",
      "verificationDescription": "Verify that unauthenticated access is rejected."
    }
  ]
}
```

**Step 2: Add it to a future release in `release-plan.json`**

Place the requirement ID in the scope of a release that comes **after** `currentVersion` in the array:

```json
{
  "currentVersion": "1.2.0",
  "releases": [
    { "version": "1.0.0", "scope": ["SYS-REQ-001", "SYS-REQ-002"] },
    { "version": "1.2.0", "scope": ["SYS-REQ-003", "SYS-REQ-007"] },
    { "version": "Door 1 Release", "scope": ["SYS-REQ-004", "SYS-REQ-012"] }
  ]
}
```

Key rules:
- **Array order determines what is deferred**, not version numbers or target dates.
- Everything after `currentVersion` in the array is treated as future.
- Release names can be anything — semver (`2.0.0`) or descriptive (`Door 1 Release`).

**Step 3: Regenerate the dashboard**

```bash
python tools/report_generator.py \
  --requirements build/demo/requirements.json \
  --behave-results build/demo/behave-results.json \
  --traceability-input build/demo/traceability_report.json \
  --output-json build/demo/final_report.json \
  --output-html build/demo/Deployment_Pipeline_Report.html \
  --sbom-path build/demo/sbom.json \
  --grype-path build/demo/grype-results.json \
  --release-plan release-plan.json
```

No need to re-run the traceability checker. The report generator reads the release plan directly and marks future-release VCs as deferred.

**What you'll see in the dashboard:**
- The VC shows as **deferred** in the Traceability Matrix
- The target release name appears in the deferred badge
- The VC does **not** count as a blocker or failure for the current release
- If the pipeline generates a stub feature file, it will include `@DEFERRED` tags automatically

---

### Scenario: A requirement is removed from the model

**Who acts:** SE exports, SE confirms removal, Developer cleans up.

1. SE removes the requirement in Cameo, runs the export macro, and pushes.
2. Pipeline runs. Gate C detects orphaned `@REQ:` and/or `@VC:` tags.
3. Pipeline fails, listing the orphaned scenarios and their files.
4. SE confirms the removal is intentional. Developer chooses one of two options:

**Option A: Delete the scenario** — Remove the feature file or the specific scenario. This is the right choice when the test is no longer valuable.

**Option B: Keep as a regression test** — If the scenario is still valuable even though the requirement is gone (e.g., it catches real bugs), remove the `@REQ:` and `@VC:` tags so the traceability checker no longer tracks it. The scenario will still run in Behave as a normal test, but it won't appear in the traceability dashboard or trigger Gate C. Replace the traceability tags with a descriptive tag like `@regression`:

```gherkin
# Before (orphaned — Gate C fails):
@REQ:SYS-REQ-099
Feature: Legacy Telemetry Validation

  @VC:SYS-REQ-099-VC-01 @VER:Test
  Scenario: Telemetry packets are within expected range

# After (regression test — invisible to traceability, still runs in Behave):
@regression
Feature: Legacy Telemetry Validation

  Scenario: Telemetry packets are within expected range
```

5. Developer commits and pushes. Pipeline passes.

### Scenario: A new VC is added to an existing requirement

**Who acts:** Same as adding a new requirement.

1. SE adds a second verification criteria to an existing requirement and exports.
2. Gate A detects the uncovered VC. A stub is generated for just the new VC.
3. Developer adds a new scenario to the existing feature file with the new `@VC:` tag.
4. No need to create a new file -- add the scenario to the existing feature file for that requirement.

### Scenario: Running the traceability checker locally

```bash
cd product-pipeline

# Full check (same as CI)
python tools/traceability_checker.py \
  --requirements build/cameo/requirements/requirements.json \
  --features-dir bdd/features \
  --stubs-output-dir bdd/features/automated \
  --non-test-output-dir bdd/features/non_test \
  --report-output build/reports/traceability/traceability_report.json \
  --fail-on-uncovered --fail-on-orphaned

# Update baseline after reviewing drift
python tools/traceability_checker.py \
  --requirements build/cameo/requirements/requirements.json \
  --features-dir bdd/features \
  --stubs-output-dir bdd/features/automated \
  --non-test-output-dir bdd/features/non_test \
  --report-output /dev/null \
  --update-baseline
```

### Scenario: Running BDD tests locally

```bash
cd product-pipeline

# Ensure logs exist (from a simulation run or sample data)
ls build/logs/product/ build/logs/simulator/ build/logs/metadata.json

# Run all automated tests
cd bdd
LOG_DIR=../build/logs python -m behave features/automated/

# Run a single feature
LOG_DIR=../build/logs python -m behave features/automated/sys_req_001_basic_comms.feature

# Run with verbose output
LOG_DIR=../build/logs python -m behave --no-capture features/automated/
```

### Troubleshooting: Pipeline fails with "uncovered verification criteria"

Check the traceability checker output for the list of uncovered VC IDs. For each one:
1. Determine if a feature file should exist (is this a new requirement?).
2. If a stub was generated, find it in `bdd/features/automated/` or `bdd/features/non_test/`.
3. Replace the stub with a real scenario. See [Writing a New Scenario](#writing-a-new-scenario).

### Troubleshooting: Pipeline fails with "@REVIEW_REQUIRED"

1. Run `git diff` on the requirements JSON to see what criteria changed.
2. Open the flagged feature file(s).
3. Check if the existing scenario steps still match the updated criteria.
4. Update steps if needed, remove `@REVIEW_REQUIRED`, update baseline, commit.

### Troubleshooting: BDD tests fail with "No product logs found"

The `LOG_DIR` environment variable must point to the directory containing `product/`, `simulator/`, and `metadata.json`. Check that:
- Simulation ran successfully and logs were collected
- `LOG_DIR` is set correctly (absolute path recommended)
- Log files are non-empty

---

## 12. Air-Gapped Environment

This pipeline is designed for disconnected networks.

| Dependency | Air-Gap Solution |
|---|---|
| Python packages | Nexus PyPI proxy or vendored wheels |
| Container images | Pre-pushed to internal registry |
| Grype vulnerability DB | Mirrored internally, `auto-update: false` |
| protoc compiler | Pre-installed on build agent |
| Helm charts | All images from internal registry |
| Gradle dependencies | Nexus Maven proxy |

No pipeline script makes external network calls. All URLs point to internal infrastructure configured via environment variables.

---

## 13. Compliance and Audit

### Traceability Chain

Every requirement can be traced through the following chain:

```
Cameo Model (requirement + VC)
    → requirements.json (versioned artifact)
        → @REQ: + @VC: tags in .feature file
            → Behave test execution (pass/fail)
                → Traceability matrix (HTML report)
                    → Release bundle
```

### Audit Trail

- **Model changes**: Git history of `exports/requirements_export.json` in `cameo-model-pipeline`
- **Criteria acknowledgments**: Git history of `.traceability-baseline.json` in `product-pipeline`
- **Test changes**: Git history of `bdd/features/` in `product-pipeline`
- **Pipeline results**: CI build artifacts (traceability report, BDD results, security scans)

### Release Bundle Contents

The final pipeline output contains everything needed for audit:

```
product-release-X.Y.Z.zip
├── helm/                           # Deployable Helm chart
├── docs/
│   ├── requirements-document.html  # Formatted requirements
│   ├── traceability-matrix.html    # Full traceability report
│   └── api-reference.html          # ICD API docs from .proto
├── security/
│   ├── sbom.json                   # CycloneDX SBOM
│   └── vulnerability-report.json   # Grype scan results
├── test-results/
│   └── behave-results.json         # Raw BDD test output
├── manifest.json                   # Build metadata, versions
└── provenance.json                 # SLSA provenance attestation
```

### NIST/DoD Compliance Mapping

| Requirement | How It's Met |
|---|---|
| SBOM for all components | Syft generates CycloneDX SBOM per container image |
| Known vulnerability disclosure | Grype scan results included in release bundle |
| Build provenance | SLSA provenance attestation |
| Artifact integrity | cosign signatures on zip and container images |
| Requirement traceability | Traceability matrix linking requirements → VCs → tests → results |
| Configuration management | Semantic versioning, Git tags, Nexus artifacts |

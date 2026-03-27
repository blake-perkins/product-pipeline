# Release Management Guide

This guide covers how to plan, track, and execute releases using the `release-plan.json` file and the pipeline's release-aware quality gates.

---

## Overview

The pipeline supports **incremental requirement delivery** across multiple releases. Not all requirements need to be satisfied before the first deployment. A `release-plan.json` file defines which requirements and verification criteria (VCs) are in scope for each release version. The pipeline enforces quality gates only on in-scope VCs and displays out-of-scope VCs as "deferred" in the dashboard.

---

## The Release Plan File

### Location

`release-plan.json` lives in the repository root. It is checked into Git and versioned alongside the code.

### Schema

```json
{
  "currentVersion": "1.2.0",
  "releases": [
    {
      "version": "1.0.0",
      "targetDate": "2026-06-01",
      "description": "Initial deployment -- core ICD communications and health monitoring",
      "scope": [
        "SYS-REQ-001",
        "SYS-REQ-002",
        "SYS-REQ-005"
      ]
    },
    {
      "version": "1.1.0",
      "targetDate": "2026-09-01",
      "description": "Degradation handling and ICD demonstration verification",
      "scope": [
        "SYS-REQ-001-VC-02",
        "SYS-REQ-003"
      ]
    },
    {
      "version": "1.2.0",
      "targetDate": "2026-12-01",
      "description": "Configuration management and data logging",
      "scope": [
        "SYS-REQ-007",
        "SYS-REQ-009",
        "SYS-REQ-011"
      ]
    },
    {
      "version": "2.0.0",
      "targetDate": "2027-03-01",
      "description": "Extended verification and system resilience",
      "scope": [
        "SYS-REQ-004",
        "SYS-REQ-006",
        "SYS-REQ-008"
      ]
    },
    {
      "version": "2.1.0",
      "targetDate": "2027-06-01",
      "description": "Full compliance and operational readiness",
      "scope": [
        "SYS-REQ-010"
      ]
    }
  ]
}
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `currentVersion` | Yes | The release version currently being developed. Must match one of the release `version` values. |
| `releases` | Yes | Array of release objects, ordered chronologically. |
| `releases[].version` | Yes | Semantic version string (e.g., `"1.0.0"`). |
| `releases[].targetDate` | No | Target ship date in `YYYY-MM-DD` format. Displayed in the dashboard. |
| `releases[].description` | No | Human-readable description of the release scope. Displayed in the dashboard. |
| `releases[].scope` | Yes | Array of requirement IDs and/or VC IDs included in this release. |

### Scope Rules

The `scope` array supports two levels of granularity:

- **Requirement ID** (e.g., `"SYS-REQ-001"`) -- includes **all VCs** under that requirement.
- **VC ID** (e.g., `"SYS-REQ-001-VC-02"`) -- includes **only that specific VC**.

This allows you to split a requirement across releases. For example, if SYS-REQ-001 has three VCs and you want two in release 1.0.0 and one in release 1.1.0:

```json
{
  "releases": [
    {
      "version": "1.0.0",
      "scope": ["SYS-REQ-001"]
    },
    {
      "version": "1.1.0",
      "scope": ["SYS-REQ-001-VC-02"]
    }
  ]
}
```

In this example, release 1.0.0 picks up all VCs from SYS-REQ-001. Release 1.1.0 explicitly adds SYS-REQ-001-VC-02 (which is already included from 1.0.0 -- duplicates are harmless). If you wanted only VC-01 and VC-03 in 1.0.0, list them individually instead of using the requirement ID.

---

## How the Pipeline Uses the Release Plan

### Current Version Resolution

The pipeline determines the current release version in this order:

1. `--release` CLI flag (highest priority, used for what-if analysis)
2. `currentVersion` field in `release-plan.json`
3. `VERSION` file in the repository root (fallback)

### Cumulative Scope

Scope is **cumulative**. The in-scope VCs for a given release include all VCs from that release **and all prior releases**. For example, if release 1.0.0 scopes SYS-REQ-001 and release 1.1.0 scopes SYS-REQ-003:

- Running the pipeline for **1.0.0**: only SYS-REQ-001 VCs are in scope.
- Running the pipeline for **1.1.0**: SYS-REQ-001 + SYS-REQ-003 VCs are in scope.
- Running the pipeline for **2.0.0**: everything from 1.0.0 + 1.1.0 + 2.0.0 is in scope.

### Effect on Quality Gates

| VC Status | In scope? | Gate A | Dashboard |
|-----------|-----------|--------|-----------|
| Has passing scenario | Yes | Pass | `pass` |
| Has failing scenario | Yes | Fail | `fail` |
| No scenario | Yes | Fail (if `--fail-on-uncovered`) | `uncovered` |
| No scenario | No (future release) | **Ignored** | `deferred` (shows target release) |
| Has scenario | No (future release) | Pass (ahead of schedule) | `pass` |
| Drifted criteria | Yes | Fail | `drifted` |
| Not in any release | -- | Warn | `unplanned` |

### Effect on Coverage Metrics

Coverage percentage is calculated against **in-scope VCs only**. Deferred VCs are excluded from both the numerator and denominator:

```
coverage = passed_in_scope / total_in_scope * 100
```

This means your coverage percentage reflects how ready the current release is, not the entire program.

---

## Release Lifecycle

### Step 1: Define the Initial Release Plan

When starting the project, create `release-plan.json` with your planned releases. Work with your systems engineers to map requirements to releases based on priority and dependencies.

```bash
# Create the file in your repo root
# Edit release-plan.json with your planned releases
git add release-plan.json
git commit -m "Add initial release plan"
```

### Step 2: Set the Current Version

Set `currentVersion` to the release you are currently working toward:

```json
{
  "currentVersion": "1.0.0",
  "releases": [...]
}
```

The pipeline will enforce gates on all VCs cumulatively scoped up to and including version 1.0.0. VCs scoped to 1.1.0 and beyond will appear as "deferred" in the dashboard.

### Step 3: Develop Against the Current Release

As you write Gherkin scenarios and fix tests, run the pipeline. The dashboard will show:

- **In-scope VCs**: must pass for the release to ship.
- **Deferred VCs**: shown with their target release version, not blocking.
- **Coverage %**: calculated against in-scope VCs only.

Use the dashboard's **global release filter** to view the state of any specific release. This is useful for checking whether prior releases are still clean or previewing what the next release looks like.

### Step 4: Ship the Release

When all in-scope VCs pass and the pipeline is green:

1. Tag the release in Git:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. Update `currentVersion` to the next release:
   ```json
   {
     "currentVersion": "1.1.0",
     "releases": [...]
   }
   ```

3. Commit and push:
   ```bash
   git add release-plan.json
   git commit -m "Advance current version to 1.1.0"
   git push
   ```

Now:
- The dashboard shows release 1.0.0 as **RELEASED** (shipped).
- VCs from 1.0.0 remain in scope (cumulative) and should continue passing.
- VCs from 1.1.0 move from "deferred" to "in scope."
- The Executive Summary shows the readiness ring for 1.1.0 as the new target.

### Step 5: Add New Releases

As the program evolves, add new releases to the plan:

```json
{
  "currentVersion": "1.1.0",
  "releases": [
    { "version": "1.0.0", "scope": ["SYS-REQ-001", "SYS-REQ-002"] },
    { "version": "1.1.0", "scope": ["SYS-REQ-003"] },
    { "version": "2.0.0", "scope": ["SYS-REQ-004", "SYS-REQ-006"] },
    { "version": "2.1.0", "scope": ["SYS-REQ-007", "SYS-REQ-008"] }
  ]
}
```

### Step 6: Move VCs Between Releases

If a VC needs to be deferred to a later release, move its ID from one release's scope to another:

**Before** (VC in 1.1.0):
```json
{ "version": "1.1.0", "scope": ["SYS-REQ-003", "SYS-REQ-007"] }
```

**After** (VC moved to 2.0.0):
```json
{ "version": "1.1.0", "scope": ["SYS-REQ-003"] },
{ "version": "2.0.0", "scope": ["SYS-REQ-004", "SYS-REQ-007"] }
```

Commit this change. The pipeline will immediately reflect the change -- the moved VCs will appear as "deferred" for 1.1.0 and "in scope" for 2.0.0.

---

## What-If Analysis

You can preview any release's state without changing `currentVersion` by using the `--release` CLI flag:

```bash
# What does 2.0.0 look like if we shipped today?
python tools/traceability_checker.py \
  --requirements build/cameo/requirements/requirements.json \
  --features-dir bdd/features \
  --release-plan release-plan.json \
  --release 2.0.0 \
  --report-output build/reports/traceability/traceability_report.json
```

This is useful for:
- Previewing whether a future release is on track.
- Checking the impact of moving VCs between releases before committing the change.
- Generating reports for release review meetings.

---

## Dashboard Release Filter

The dashboard includes a **global release filter** dropdown in the hero header. This is a client-side filter that scopes every tab to a specific release:

- **All Releases**: shows everything (default).
- **Release X.Y.Z (Released)**: shows the state at the time of release -- all gates pass, no orphans, no vulnerabilities, shipped confirmation in Executive Summary.
- **Release X.Y.Z (Current)**: shows the current working state with all issues.
- **Release X.Y.Z** (future): shows what's in scope if that were the current release.

The filter is cumulative -- selecting 1.1.0 shows VCs from both 1.0.0 and 1.1.0.

The hero header's Release Scope card shows the **release-specific** VC count (not cumulative), matching the Release Progress tab. The Traceability Matrix, Quality Gates, Test Execution, and Cyber tabs all filter to the cumulative scope.

---

## Unplanned Requirements

If a requirement exists in `requirements.json` but is not listed in any release's scope, it will appear in the dashboard but will not be categorized under any release. The pipeline will still run quality gates on it (it's treated as in-scope for all releases). To defer it, add it to a future release's scope.

---

## Common Scenarios

### New requirement added to the Cameo model

1. Systems engineer exports the updated model.
2. The pipeline detects the new requirement and its VCs.
3. If the new VCs are not in any release scope, they appear as in-scope for the current release.
4. Add the new requirement to the appropriate release in `release-plan.json`.
5. If it belongs to a future release, the VCs become "deferred" and no longer block the current release.

### Requirement removed from the Cameo model

1. Systems engineer exports the updated model.
2. The pipeline detects that existing Gherkin scenarios reference a deleted requirement (Gate C -- orphan detection).
3. Developers remove or reassign the orphaned scenarios.
4. Remove the requirement from the `release-plan.json` scope.

### Scope change mid-release

1. Edit `release-plan.json` to move VCs between releases.
2. Commit and push.
3. The pipeline immediately reflects the change -- no other files need to change.
4. Deferred VCs stop blocking Gate A; newly in-scope VCs start blocking it.

### Verifying a release is ready to ship

1. Open the dashboard.
2. Select the target release from the global filter dropdown.
3. Check the Executive Summary readiness ring.
4. Verify all quality gates pass.
5. Review the Traceability Matrix for any remaining issues.
6. If the readiness ring shows 100% and no items remain, the release is ready.

### Reviewing a shipped release

1. Open the dashboard.
2. Select the shipped release from the dropdown (marked "Released").
3. All gates show as passed, the Executive Summary shows a shipped confirmation.
4. The Traceability Matrix shows the VCs that were in scope with their pass status.
5. The Cyber tab shows a clean scan (vulnerabilities were resolved before shipping).

# Migration Guide: v0.2.0 to v0.3.0

This guide covers the breaking changes in v0.3.0. If you are migrating from v0.1.x, follow the [v0.2.0 migration guide](MIGRATION-v0.2.0.md) first.

## What Changed

### 1. Full Rename: "Verification Method" → "Verification Criteria" (Breaking)

Every reference to "Verification Method" and "VM" has been renamed to "Verification Criteria" and "VC" — in the data model, Gherkin tags, Python code, and all documentation.

#### JSON Fields

| v0.2.0 | v0.3.0 |
|--------|--------|
| `verificationMethods` | `verificationCriteria` |
| `verificationMethodId` | `verificationCriteriaId` |

**Before (v0.2.0):**
```json
{
  "requirementId": "SYS-REQ-001",
  "verificationMethods": [
    {
      "verificationMethodId": "SYS-REQ-001-VM-01",
      "method": "Test",
      "criteria": "Verify that..."
    }
  ]
}
```

**After (v0.3.0):**
```json
{
  "requirementId": "SYS-REQ-001",
  "verificationCriteria": [
    {
      "verificationCriteriaId": "SYS-REQ-001-VC-01",
      "method": "Test",
      "criteria": "Verify that..."
    }
  ]
}
```

#### Scoped IDs

| v0.2.0 | v0.3.0 |
|--------|--------|
| `SYS-REQ-001-VM-01` | `SYS-REQ-001-VC-01` |
| `-VM-` in ID format | `-VC-` in ID format |

#### Gherkin Tags

| v0.2.0 | v0.3.0 |
|--------|--------|
| `@VM:SYS-REQ-001-VM-01` | `@VC:SYS-REQ-001-VC-01` |

### 2. New Features (Non-Breaking)

These features were added in v0.3.0 and don't require migration — they're optional enhancements:

- **Release planning** (`release-plan.json`) — map requirements/VCs to release versions
- **Deferred VCs** — out-of-scope VCs for the current release show as "deferred" instead of blocking
- **Interactive dashboard** — 6-tab HTML dashboard with drill-down traceability, release progress, quality gates, test execution, cyber (SBOM/Grype), and export
- **Word-level diff** for drifted verification criteria
- **Dashboard tests** — 106 pytest tests running in CI

---

## Migration Steps

### Step 1: Update Both Repos

```bash
cd cameo-model-pipeline && git pull origin master
cd product-pipeline && git pull origin master
```

### Step 2: Re-export from Cameo

The Groovy macro now outputs `verificationCriteria` (not `verificationMethods`) and `verificationCriteriaId` (not `verificationMethodId`) with `-VC-` IDs.

Re-run the export macro in Cameo and commit the updated `exports/requirements_export.json`.

**If manually maintaining JSON:** Rename the fields and IDs:

```
verificationMethods        →  verificationCriteria
verificationMethodId       →  verificationCriteriaId
SYS-REQ-001-VM-01          →  SYS-REQ-001-VC-01
```

### Step 3: Update Gherkin Tags in Feature Files

Find and replace in all `.feature` files:

```bash
# In your feature files directory:
find bdd/features -name "*.feature" -exec sed -i 's/@VM:/@VC:/g; s/-VM-/-VC-/g' {} +
```

**Before:**
```gherkin
@REQ:SYS-REQ-001
Feature: Basic ICD Communications

  @VM:SYS-REQ-001-VM-01 @VER:Test
  Scenario: Valid request produces response
```

**After:**
```gherkin
@REQ:SYS-REQ-001
Feature: Basic ICD Communications

  @VC:SYS-REQ-001-VC-01 @VER:Test
  Scenario: Valid request produces response
```

### Step 4: Update release-plan.json (If Using)

If you created a `release-plan.json`, update any VC-level scope entries:

```
SYS-REQ-001-VM-02  →  SYS-REQ-001-VC-02
```

Requirement-level scope entries (e.g., `SYS-REQ-001`) don't need changes.

### Step 5: Reset the Traceability Baseline

The baseline uses VC IDs as keys. Delete and regenerate:

```bash
rm bdd/features/.traceability-baseline.json

python tools/traceability_checker.py \
  --requirements build/cameo/requirements/requirements.json \
  --features-dir bdd/features \
  --stubs-output-dir bdd/features/automated \
  --non-test-output-dir bdd/features/non_test \
  --report-output /dev/null \
  --update-baseline
```

### Step 6: Run Locally to Verify

```bash
# Traceability check
python tools/traceability_checker.py \
  --requirements build/cameo/requirements/requirements.json \
  --features-dir bdd/features \
  --stubs-output-dir bdd/features/automated \
  --non-test-output-dir bdd/features/non_test \
  --report-output build/reports/traceability/traceability_report.json \
  --fail-on-orphaned

# Tests
python -m pytest tests/ -v

# Commit and push
```

---

## Backward Compatibility

The tools accept **both old and new field names** during the transition:

- `verificationCriteria` is tried first; falls back to `verificationMethods`
- `verificationCriteriaId` is tried first; falls back to `verificationMethodId`
- `@VC:` tags are the primary pattern; `@VM:` tags are **no longer recognized**

**Important:** The Gherkin tag change (`@VM:` → `@VC:`) has **no backward compatibility**. You must update all feature files. The traceability checker will not find scenarios tagged with `@VM:`.

---

## Quick Reference

| What | Find | Replace With |
|------|------|-------------|
| JSON array field | `verificationMethods` | `verificationCriteria` |
| JSON ID field | `verificationMethodId` | `verificationCriteriaId` |
| Scoped ID | `-VM-` | `-VC-` |
| Gherkin tag | `@VM:` | `@VC:` |
| Display text | "Verification Method" | "Verification Criteria" |
| Abbreviation | "VM" | "VC" |

# Release Notes

## v0.3.0 (Verification Criteria Rename + Release Filter)

### New Features
- Executive Summary tab added to the interactive dashboard with release readiness ring
- Global release filter dropdown that scopes the entire dashboard to a specific release version
- Release planning system (`release-plan.json`) with support for deferred VCs that do not block Gate A
- "Verification Method" renamed to "Verification Criteria" throughout the data model, codebase, and documentation
- Shipped state tracking for released versions
- Centralized filter architecture (`buildSnapshot`) powering all dashboard tabs
- 232 pytest tests (unit + demo integration)

### Breaking Changes
- JSON fields renamed: `verificationMethods` -> `verificationCriteria`, `verificationMethodId` -> `verificationCriteriaId`
- Scoped IDs changed from `-VM-` to `-VC-` (e.g., `SYS-REQ-001-VM-01` -> `SYS-REQ-001-VC-01`)
- Gherkin tags changed from `@VM:` to `@VC:` -- no backward compatibility at the tag level

### Migration
- See `docs/MIGRATION-v0.3.0.md` for detailed migration instructions.

---

## v0.2.0 (Interactive Dashboard)

### New Features
- 6-tab interactive HTML dashboard: Traceability Matrix, Quality Gates, Release Progress, Test Execution, Cyber, Export & Info
- Hero header with three clickable KPI cards (Release Scope, Test Results, Blockers)
- Drill-down accordion for per-requirement detail in the Traceability Matrix tab
- SBOM and Grype integration in the Cyber tab
- Word-level diff display for drifted verification criteria in the Quality Gates tab
- Cross-tab navigation with flash highlighting
- Self-contained HTML output with zero external dependencies (air-gapped compatible)

### Breaking Changes
- Data model changed to support 1-to-many verification criteria per requirement
- `@VC:` tag now required at the scenario level to link scenarios to individual verification criteria

---

## v0.1.0 (Initial Release)

### New Features
- Initial product pipeline setup
- Cameo model integration with traceability quality gates
- BDD test framework with post-run log analysis
- Syft/Grype security scanning
- Helm chart for multi-container and single-container deployment
- Automated traceability matrix report generation

### Known Issues
- None (initial release)

### Breaking Changes
- N/A (initial release)

# Release Notes

## v0.4.0 (Interactive Dashboard + Release Management)

### New Features
- 7-tab interactive Deployment Pipeline Report (titled "Deployment Pipeline Report") replacing the flat HTML report
- Dashboard output filename: `MBSE_Traceability_Dashboard.html`
- Dark mode toggle (Light / Dark button) for switching between light and dark themes
- Amber `--attention` color for pipeline badge and blockers (not red)
- Readiness ring moved into the Release Scope hero card (not a standalone section in Executive Summary)
- `@DEFERRED` Gherkin tag for deferred VCs
- Demo data banner at bottom for DemoSystem projects
- Executive Summary tab with top issues, cyber risk summary
- Global release filter dropdown scoping the entire dashboard to a specific release
- Centralized filter architecture (`buildSnapshot`) powering all dashboard tabs
- Release planning system with `release-plan.json` and deferred VCs
- SBOM/vulnerability integration in the Cyber tab (Syft + Grype)
- Hero header with three clickable KPI cards (Release Scope, Test Results, Blockers)
- Cross-tab navigation with yellow flash highlighting
- Shipped confirmation state for released versions
- Deferred and stub features filtered from Test Execution tab
- Grey severity cards for zero-count CVEs on Cyber tab
- Demo data generator exercising all dashboard states
- 232 pytest tests (unit + demo + SBOM integration)
- Dedicated release management guide (`docs/guides/release-management.md`)

### Breaking Changes
- Dashboard HTML output is a completely new format (7-tab SPA replaces flat table)
- Pipeline job renamed from `traceability-report` to `traceability-dashboard`
- Documentation reorganized into `docs/guides/`, `docs/migration/`, `docs/presentations/`

### Migration
- See `docs/migration/v0.4.0.md` for detailed migration instructions.

---

## v0.3.0 (Verification Criteria Rename)

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
- See `docs/migration/v0.3.0.md` for detailed migration instructions.

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

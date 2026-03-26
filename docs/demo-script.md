# MBSE Traceability Dashboard: Customer Demo Script

**Duration:** ~10 minutes
**Audience:** Non-technical stakeholders, program managers, leadership
**Setup:** Open `MBSE_Traceability_Dashboard.html` in a browser. The dashboard defaults to Release 1.0.0 (green, shipped). No other setup needed.

---

## Opening (0:00 - 1:00)

**What you see:** A clean, green dashboard showing Release 1.0.0 with "Pipeline Pass" badge.

**Say:**
> "This is the MBSE Traceability Dashboard. It's a single HTML file produced by our CI/CD pipeline on every build. No server, no installation -- you download it and open it in your browser. It works completely offline."

Point at the three hero cards:
> "At a glance, you see three things: what's in scope for this release, how many tests passed, and whether there are any blockers."

Point at the dropdown:
> "This dropdown lets us look at any release. Right now we're looking at Release 1.0.0, which already shipped. Let me show you what that looks like."

---

## Act 1: Release 1.0.0 -- The Clean Baseline (1:00 - 2:30)

**Filter:** Release 1.0.0 (Released) -- already selected on load.

**Say:**
> "Everything is green. Three requirements, three passing tests, zero blockers. This release shipped clean."

Click **Executive Summary** tab (if not already active):
> "The shipped confirmation tells us this release went out successfully. Four verification criteria, all passed."

Click **Traceability Matrix** tab. Expand SYS-REQ-001 (Basic ICD Communications):
> "Here's the key: every requirement from the Cameo model traces directly to a test. Open any requirement and you see the verification criteria, the Gherkin scenario, and every test step -- Given, When, Then -- with pass/fail status."

> "If a requirement exists in the model but has no test, the pipeline catches it. If a test exists but its requirement was removed, the pipeline catches that too."

Click **Quality Gates** tab:
> "Three automated gates run on every build. Gate A checks that every requirement has a test. Gate B detects when the Cameo model changes. Gate C finds stale tests pointing at deleted requirements. All three pass here."

**Takeaway:** The audience understands what the dashboard shows and what traceability means.

---

## Act 2: Release 1.1.0 -- Building On It (2:30 - 3:30)

**Filter:** Select "Release 1.1.0 (Released)"

**Say:**
> "Release 1.1.0 added error handling. Also green -- it shipped clean."

Quick look at Traceability Matrix -- show the additional requirement (SYS-REQ-005):
> "The pipeline enforced coverage. The team had to write a test for this new requirement before the release could pass. Gate A ensured nothing slipped through."

> "Two releases shipped. Both clean. Now let's look at what's in progress."

**Takeaway:** The audience sees how incremental releases work.

---

## Act 3: Release 1.2.0 -- The Model Changed (3:30 - 6:30)

**Filter:** Select "Release 1.2.0 (Current)"

The hero animates -- numbers count up, the badge turns red, blockers appear.

**Say:**
> "This is our current release. The pipeline caught three things -- one for each quality gate."

Point at the Readiness ring in Executive Summary:
> "We're at about 63% readiness. A few items to resolve before this can ship."

Click the **failed test** (SYS-REQ-007-VC-01) in the Top Issues section:
- The dashboard switches to Traceability Matrix and highlights the failing VC with a yellow flash.

**Say:**
> "Gate A -- Coverage -- caught a test failure. A configuration update is taking 12 seconds instead of the required 5. The developer can see exactly which requirement it traces to, what the test expected, and the actual error message. No guessing."

Navigate back to **Executive Summary** tab. Click the **drifted VC** (SYS-REQ-003-VC-01):
- The dashboard shows the word-level diff: green highlight on the added text.

**Say:**
> "Gate B -- Drift Detection. A systems engineer updated the model in Cameo -- they added a requirement for automatic failover. The pipeline detected the text changed and flagged it. See the green highlight showing exactly what was added. The test needs to be updated to cover the new criteria."

Pause to let them read the diff.

Navigate to **Quality Gates** tab. Point at Gate C:
> "Gate C -- Orphan Detection. Someone deleted a requirement from the model, but a test still references it. The pipeline flagged it so the team can clean it up. Without this, you'd have stale tests giving you false confidence."

> "All three of these issues are scoped to Release 1.2.0. They don't affect the releases we already shipped. The pipeline knows the difference."

**Takeaway:** The audience sees all three quality gates catching real problems -- a failing test, a model change, and a stale test -- with full traceability back to the model.

---

## Act 4: Release 2.0.0 -- Planning Ahead (6:30 - 8:00)

**Filter:** Select "Release 2.0.0"

**Say:**
> "This is a future release. Nothing here blocks our current work."

Show the deferred VCs in the Traceability Matrix:
> "These requirements are planned for 2.0.0. The pipeline tracks them but doesn't enforce them yet. When we advance to this release, they become mandatory."

Point out the uncovered VC (SYS-REQ-008-VC-01):
> "One requirement doesn't have a test yet. The pipeline generated a placeholder -- the developer just fills in the steps when the time comes."

Click **Release Progress** tab:
> "Here's the full roadmap. Five releases with progress bars, target dates, and clickable details. You can see at a glance where the program stands."

> "The team can plan ahead without future work blocking their current release."

**Takeaway:** The audience understands deferred VCs and release planning.

---

## Act 5: Cyber (8:00 - 9:00)

Stay on Release 2.0.0 or select "All Releases."

Click **Cyber** tab:

**Say:**
> "We also scan every container image for known vulnerabilities."

Point at the SBOM section:
> "This is the software bill of materials -- every component in the deployed artifact, with versions and sources."

Point at the vulnerability table:
> "The scanner found seven vulnerabilities, including one critical in OpenSSL. The policy banner at the top says we can't ship until it's resolved."

Point at the severity cards:
> "The team can filter by severity, search for specific CVEs, or download the full list as a CSV for their security review."

**Takeaway:** The audience sees how cyber scanning integrates into the same dashboard.

---

## Closing (9:00 - 10:00)

**Filter:** Select "All Releases"

**Say:**
> "One HTML file. Every requirement traced from model to test to result. Three automated quality gates. Release-aware planning. Cyber scanning. Works completely offline in air-gapped environments."

Click **Export & Info** tab:
> "You can print it, download the raw data as JSON, or reference the glossary."

> "This is produced automatically on every pipeline run. No manual report writing. Questions?"

---

## Tips for the Presenter

- **Start on 1.0.0** (the dashboard defaults to it). Green first, problems later.
- **Let the animations land.** When switching to 1.2.0, the numbers counting up and the red badge appearing create a moment. Don't talk over it.
- **The cross-tab navigation is a wow moment.** When you click an issue and the dashboard flies to the exact VC with the yellow flash -- pause and let them see it.
- **The word-level diff is a wow moment.** The green highlight showing exactly what the systems engineer changed is very visual. Pause on it.
- **Don't explain every tab.** The audience doesn't need to understand Gherkin syntax or SBOM formats. Keep it at the "what does this mean for you" level.
- **If asked about manual verification (Analysis/Inspection):** "The pipeline supports all four INCOSE verification methods. For this demo we focused on automated tests, but Analysis and Inspection requirements can also be tracked."
- **If asked about integration:** "This consumes standard formats -- JSON from Cameo, Behave test results, CycloneDX SBOMs, Grype scan output. It plugs into any CI/CD pipeline."

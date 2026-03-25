# Product Pipeline

**Model-driven verification pipeline: from Cameo system model to signed release bundle.**

A Gradle-orchestrated pipeline that fetches MagicDraw/Cameo model artifacts from Nexus, enforces traceability quality gates between requirements and BDD scenarios, deploys the product and simulator into Kubernetes, runs simulation-based verification, performs post-run log analysis with Behave, executes security scanning, and produces a cosign-signed release bundle with SLSA provenance. Designed for air-gapped DoD/NIST environments.

---

## Architecture Overview

```
                         PRODUCT PIPELINE — END-TO-END FLOW
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                                                                             │
 │  ┌──────────────┐    ┌───────────────────┐    ┌──────────────────────────┐  │
 │  │  Nexus Repo   │───>│ Fetch Cameo ZIP   │───>│  Traceability Check     │  │
 │  │ (Cameo model  │    │ (Gradle)          │    │  (3 Quality Gates)      │  │
 │  │  artifacts)   │    └───────────────────┘    │  A: Uncovered Reqs      │  │
 │  └──────────────┘                              │  B: Criteria Drift      │  │
 │                                                │  C: Orphaned Scenarios  │  │
 │                                                └──────────┬───────────────┘  │
 │                                                           │                 │
 │                                                           v                 │
 │  ┌──────────────────────────────────────────────────────────────────────┐   │
 │  │               Deploy to Kubernetes (Helm)                           │   │
 │  │  ┌─────────────────────┐    ┌──────────────────────┐                │   │
 │  │  │  Product Chart       │    │  Simulator Chart      │               │   │
 │  │  │  (multi-container    │    │  (protobuf ICD        │               │   │
 │  │  │   or single)         │◄──►│   stimulus)           │               │   │
 │  │  └─────────────────────┘    └──────────────────────┘                │   │
 │  └──────────────────────────────────┬───────────────────────────────────┘   │
 │                                     │                                       │
 │                                     v                                       │
 │  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────┐  │
 │  │  Collect Logs     │───>│  BDD Log Analysis │───>│  Security Scan       │  │
 │  │  (kubectl logs)   │    │  (Behave)         │    │  (Syft SBOM +        │  │
 │  │                   │    │  Pure file I/O    │    │   Grype CVE)         │  │
 │  └──────────────────┘    └──────────────────┘    └──────────┬───────────┘  │
 │                                                              │              │
 │                                                              v              │
 │  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────┐  │
 │  │  Generate Reports │───>│  Package Release  │───>│  Sign with cosign    │  │
 │  │  (Traceability    │    │  Bundle (.zip)    │    │  + SLSA Provenance   │  │
 │  │   Matrix, HTML)   │    │                   │    │                      │  │
 │  └──────────────────┘    └──────────────────┘    └──────────┬───────────┘  │
 │                                                              │              │
 │                                                              v              │
 │                                                     ┌───────────────┐      │
 │                                                     │  Publish to    │      │
 │                                                     │  Nexus / OCI   │      │
 │                                                     │  Registry      │      │
 │                                                     └───────────────┘      │
 └─────────────────────────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
product-pipeline/
├── build.gradle                    # Gradle build: tasks for fetch, trace, deploy, test, scan, release
├── versions.properties             # Single source of truth for all version pins
├── settings.gradle                 # Gradle settings
├── gradle.properties               # Gradle properties
├── Jenkinsfile                     # Jenkins declarative pipeline (K8s pod agents)
├── .github/
│   └── workflows/
│       └── product-pipeline.yml    # GitHub Actions workflow
├── bdd/
│   ├── behave.ini                  # Behave configuration
│   ├── requirements.txt            # Python deps (behave, etc.)
│   ├── proto/                      # Protobuf definitions for ICD messages
│   └── features/
│       ├── environment.py          # Behave hooks: loads logs from disk, skips @manual
│       ├── automated/              # Auto-runnable BDD feature files
│       │   └── sys_req_001_basic_comms.feature
│       ├── non_test/               # Non-Test verification stubs (@manual)
│       └── steps/
│           └── log_analysis_steps.py   # Step defs: pure log assertions
├── docs/
│   ├── guides/                     # Pipeline, release management, installation, user guides
│   ├── migration/                  # Version migration guides (v0.2.0, v0.3.0)
│   ├── presentations/              # Executive briefs and slide decks
│   └── release-notes.md            # Release notes per version
├── helm/
│   ├── product-chart/              # Multi-container product deployment
│   ├── simulator-chart/            # Simulator for ICD stimulus
│   └── single-container-chart/     # Single-container deployment for isolated testing
├── scripts/
│   ├── run_simulations.sh          # Deploy, simulate, collect logs, teardown
│   ├── package_release.sh          # Assemble release bundle zip
│   ├── sign_artifacts.sh           # cosign signing for release artifacts
│   └── generate_provenance.sh      # SLSA v0.2 provenance attestation
├── security/
│   ├── scan.sh                     # Syft SBOM generation + Grype vulnerability scan
│   └── grype-policy.yaml           # CVE severity thresholds and ignore rules
├── simulator/
│   └── helm/                       # Simulator Helm chart source
└── tools/
    ├── traceability_checker.py     # Core quality gate engine (Gates A/B/C)
    ├── stub_generator.py           # Auto-generates stub .feature files
    ├── report_generator.py         # Merges requirements + BDD results into reports
    ├── generate_req_doc.py         # HTML requirements document generator
    ├── requirements.txt            # Python deps for tools
    └── templates/
        └── stub_scenario.feature.j2    # Jinja2 template for stub generation
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Java (JDK) | 17+ | Gradle runtime |
| Gradle | 8.x (wrapper included) | Build orchestration |
| Python | 3.10+ | Traceability checker, stub generator, Behave BDD, report generation |
| Helm | 3.x | Kubernetes deployments |
| kubectl | Compatible with target cluster | Pod management, log collection |
| Kubernetes cluster | 1.25+ | Runtime environment for product and simulator |
| cosign | 2.x | Artifact signing (supply chain security) |
| Syft | Latest | SBOM generation |
| Grype | Latest | Container vulnerability scanning |

Python package dependencies are managed via `tools/requirements.txt` (for pipeline tools) and `bdd/requirements.txt` (for Behave and step libraries).

---

## Quick Start

### 1. Fetch and unpack the Cameo model

```bash
./gradlew unpackCameoZip -PnexusUrl=https://nexus.internal.example.com/repository/maven-releases/
```

### 2. Run traceability quality gates

```bash
python3 tools/traceability_checker.py \
    --requirements build/cameo/requirements/requirements.json \
    --features-dir bdd/features \
    --stubs-output-dir bdd/features/automated \
    --non-test-output-dir bdd/features/non_test \
    --report-output build/reports/traceability/traceability_report.json \
    --html-report-output build/reports/traceability/traceability_report.html \
    --fail-on-uncovered \
    --fail-on-orphaned
```

### 3. Run simulations (requires K8s cluster)

```bash
bash scripts/run_simulations.sh test build/logs pod 300
```

### 4. Run BDD log analysis

```bash
cd bdd
LOG_DIR=../build/logs python3 -m behave \
    --format json --outfile ../build/reports/bdd/behave-results.json \
    --format pretty --no-capture features/
```

### 5. Generate the interactive dashboard

```bash
python3 tools/report_generator.py \
    --requirements build/cameo/requirements/requirements.json \
    --behave-results build/reports/bdd/behave-results.json \
    --traceability-input build/reports/traceability/traceability_report.json \
    --output-json build/reports/traceability/traceability_report.json \
    --output-html build/reports/traceability/traceability_report.html
```

The HTML output is a self-contained 7-tab interactive dashboard with zero external dependencies (air-gapped compatible):

| Tab | Content |
|-----|---------|
| **Executive Summary** | Release readiness ring, top-level KPIs |
| **Traceability Matrix** | Requirements-to-test coverage with drill-down accordion |
| **Quality Gates** | Gate A/B/C status with word-level drift diffs |
| **Release Progress** | Per-release scope tracking with deferred VC handling |
| **Test Execution** | Behave scenario results and pass/fail breakdown |
| **Cyber** | SBOM and Grype vulnerability summary |
| **Export & Info** | Data export and pipeline metadata |

A global release filter dropdown scopes the entire dashboard to a specific release version. The hero header displays three clickable KPI cards (Release Scope, Test Results, Blockers) with cross-tab navigation and flash highlighting.

### 6. Run the full pipeline via Gradle

```bash
./gradlew generateTraceabilityReport securityScan --no-daemon
```

### 7. Update the traceability baseline (after reviewing drift)

```bash
python3 tools/traceability_checker.py \
    --requirements build/cameo/requirements/requirements.json \
    --features-dir bdd/features \
    --stubs-output-dir bdd/features/automated \
    --report-output /dev/null \
    --update-baseline
```

---

## The Three Quality Gates

The traceability checker (`tools/traceability_checker.py`) enforces three quality gates that run against every build. All three must pass for the pipeline to proceed.

### Gate A: Uncovered Verification Criteria

**Problem:** A verification criteria (VC) exists in the Cameo model but has no corresponding BDD scenario.

**Behavior:**
- Scans all `.feature` files for `@VC:<id>` tags and compares against the requirements JSON export.
- For any uncovered VC, auto-generates a stub `.feature` file using the Jinja2 template (`tools/templates/stub_scenario.feature.j2`).
- Test/Demonstration VCs generate stubs in `bdd/features/automated/`.
- Analysis/Inspection VCs generate stubs in `bdd/features/non_test/` with the `@manual` tag.
- Generated stubs contain a deliberately failing step (`Then it should fail because it is not yet implemented`) to keep the pipeline red until real verification is authored.
- When `--fail-on-uncovered` is set, the gate fails the pipeline.
- **Release planning:** When a `release-plan.json` is provided, VCs that are out-of-scope for the current release are marked as **deferred** and do not count toward Gate A failure.

### Gate B: Verification Criteria Drift

**Problem:** The `criteria` text for a verification criteria changed in the Cameo model, but the corresponding BDD scenarios have not been reviewed.

**Behavior:**
- Compares SHA-256 hashes of current criteria text against a stored baseline (`.traceability-baseline.json`).
- The baseline also stores the original criteria text, enabling word-level diff display in the dashboard.
- When drift is detected, injects the `@REVIEW_REQUIRED` tag into all affected `.feature` files.
- Always fails the pipeline when drift is found — forces human review.
- To resolve: update the BDD scenarios, remove `@REVIEW_REQUIRED` tags, and run `--update-baseline`.

### Gate C: Orphaned Scenarios

**Problem:** A BDD scenario references a requirement or VC ID (via `@REQ:<id>` or `@VC:<id>`) that no longer exists in the Cameo model.

**Behavior:**
- Identifies scenarios whose `@REQ` or `@VC` tags point to deleted or renamed requirements/VCs.
- When `--fail-on-orphaned` is set, the gate fails the pipeline.
- Orphaned scenarios can be kept as regression tests by removing the `@REQ:`/`@VC:` tags (see pipeline guide).

### Gherkin Tag Conventions

| Tag | Meaning |
|-----|---------|
| `@REQ:<id>` | Links a feature to a Cameo requirement (e.g., `@REQ:SYS-REQ-001`). Applied at **feature level**. |
| `@VC:<id>` | Links a scenario to a specific verification criteria (e.g., `@VC:SYS-REQ-001-VC-01`). Applied at **scenario level**. |
| `@VER:<method>` | Declares the INCOSE verification criteria (e.g., `@VER:Test`) |
| `@STUB` | Marks an auto-generated stub awaiting real implementation |
| `@AUTO_GENERATED` | Indicates the file was machine-generated |
| `@manual` | Skipped by automated Behave runs; requires human verification |
| `@REVIEW_REQUIRED` | Injected by Gate B; indicates criteria drift needing human review |
| `@regression` | Test kept for regression value after its requirement was removed |
| `@topology:<type>` | Scenario only runs under the specified deployment topology |

---

## Test Execution Model

This pipeline uses a **post-run log analysis** pattern, not live system interaction during BDD execution.

### How It Works

1. **Simulator stimulates the product.** The simulator pod sends protobuf ICD messages to the product pod(s) according to predefined scenarios. The product processes these messages and produces structured JSON log output.

2. **Pipeline script orchestrates the lifecycle.** `scripts/run_simulations.sh` handles the full sequence:
   - Deploy the product (via Helm, topology-dependent)
   - Deploy the simulator
   - Wait for simulation completion (with configurable timeout)
   - Collect logs from all pods via `kubectl logs`
   - Tear down simulator and product

3. **Behave performs ONLY post-run log analysis.** The BDD step definitions (`bdd/features/steps/log_analysis_steps.py`) perform pure file I/O assertions against the collected log files. There are no network calls, no `kubectl` invocations, and no container interaction during Behave execution. The `environment.py` hooks load all log files and run metadata into the Behave context at startup.

4. **Structured JSON log format.** The product and simulator emit newline-delimited JSON logs with fields including `timestamp`, `level`, `component`, `message`, `request_id`, and `status`. Step definitions parse these entries for timing analysis, content assertions, and error detection.

### Key Design Decisions

- Behave is decoupled from the cluster. This enables local development, CI replay with recorded logs, and air-gapped testing.
- Scenarios tagged `@manual` are automatically skipped by the `before_scenario` hook.
- Scenarios tagged `@topology:<type>` are skipped when the active topology does not match.

---

## Deployment Topologies

The pipeline supports two deployment topologies, controlled by `deploy.topology` in `versions.properties`:

### Pod Topology (`deploy.topology=pod`)

The default. Deploys the full multi-container pod:
- **container-a** — Primary product container (port 50051)
- **container-b** — Secondary product container (port 50052)
- **sidecar** — Sidecar process

All three images and their versions are pinned in `versions.properties`:
```properties
container.a.image=product/container-a
container.a.version=0.1.0
container.b.image=product/container-b
container.b.version=0.1.0
sidecar.image=product/sidecar
sidecar.version=0.1.0
```

### Single Topology (`deploy.topology=single`)

Deploys a single container image for isolated testing. Uses the `single-container-chart` Helm chart:
```properties
single.container.image=product/container-a
single.container.version=0.1.0
```

Switch between topologies by editing `versions.properties` or overriding via environment:
```bash
./gradlew runSimulations -Pdeploy.topology=single
```

---

## Helm Charts

Three Helm charts are provided under `helm/`:

| Chart | Description | Values |
|-------|-------------|--------|
| `product-chart` | Multi-container C++ product deployment. Defines container-a, container-b, and sidecar with resource limits, image pull secrets, and ClusterIP service. | `helm/product-chart/values.yaml` |
| `simulator-chart` | Simulator that stimulates the product under test with ICD (protobuf) messages. | `helm/simulator-chart/` |
| `single-container-chart` | Single container deployment for isolated testing. Used when `deploy.topology=single`. | `helm/single-container-chart/` |

The product chart default values configure:
- Image pull from `registry.internal.example.com`
- CPU/memory resource requests and limits per container
- ClusterIP service on port 8080
- Image pull secret via `registry-credentials`

Charts are packaged and published to the internal OCI Helm registry on the `main` branch:
```bash
helm package helm/product-chart --version 0.1.0 --destination build/helm
helm push build/helm/product-chart-0.1.0.tgz oci://registry.internal.example.com/helm-charts
```

---

## Security Scanning

Security scanning runs via `security/scan.sh` and targets all product container images based on the active deployment topology.

### Syft -- SBOM Generation

Generates a Software Bill of Materials in CycloneDX JSON format for each container image:
```bash
syft <registry>/<image>:<tag> -o cyclonedx-json > sbom.json
```

### Grype -- CVE Vulnerability Scan

Scans the generated SBOM against known vulnerability databases:
```bash
grype sbom:sbom.json -o json > grype-results.json
```

Policy enforcement is configured via `security/grype-policy.yaml`, which defines severity thresholds and CVE ignore rules. The scan fails the pipeline if vulnerabilities exceed the configured policy.

### Outputs

- `build/reports/security/sbom.json` — CycloneDX SBOM
- `build/reports/security/grype-results.json` — Vulnerability scan results

---

## Release Bundle

The release bundle is assembled by `scripts/package_release.sh` into a versioned zip file:

```
product-release-<version>/
├── helm/
│   └── product-chart-<version>.tgz        # Packaged Helm chart
├── docs/
│   ├── installation-guide/                 # Installation documentation
│   ├── user-guide/                         # User documentation
│   ├── release-notes/                      # Version release notes
│   ├── requirements-document.html          # Auto-generated from Cameo model
│   └── traceability-matrix.html            # Interactive 7-tab dashboard (see below)
├── security/
│   ├── sbom.json                           # Software Bill of Materials
│   └── grype-results.json                  # Vulnerability scan results
└── test-results/
    ├── behave-results.json                 # BDD test results
    └── traceability_report.json            # Quality gate results
```

---

## Artifact Signing and Provenance

### cosign Signing

Release artifacts are signed using [cosign](https://github.com/sigstore/cosign) via `scripts/sign_artifacts.sh`:

```bash
./scripts/sign_artifacts.sh build/release/product-release-0.1.0.zip --key cosign.key
```

In air-gapped environments, signing uses a local key pair rather than Fulcio/Rekor. The cosign private key path and password are configured via:
- `COSIGN_KEY` environment variable (default: `cosign.key`)
- `COSIGN_PASSWORD` environment variable

Container images in the registry can also be signed:
```bash
cosign sign --key cosign.key <registry>/<image>@<digest>
```

### SLSA Provenance

`scripts/generate_provenance.sh` generates a [SLSA v0.2](https://slsa.dev) provenance attestation (in-toto Statement v0.1) for the release bundle:

```bash
./scripts/generate_provenance.sh build/release/product-release-0.1.0.zip build/provenance.json
```

The provenance document captures the build environment, source commit, builder identity, and artifact digests for supply chain verification.

---

## CI/CD

### GitHub Actions

Defined in `.github/workflows/product-pipeline.yml`. Runs on pushes and pull requests to `main`.

**Jobs:**
1. `fetch-model` — Checkout, setup Java 17 + Gradle, fetch and unpack Cameo model from Nexus. Falls back to sample data if Nexus is unavailable (prototype mode).
2. `traceability-check` — Install Python tools, run all three quality gates.
3. `bdd-tests` — Install Behave dependencies, run BDD log analysis. Uses pre-recorded sample logs in prototype/CI mode.
4. `traceability-report` — Merge requirements, BDD results, and gate output into the interactive HTML dashboard and JSON report.

Artifacts are uploaded between jobs via `actions/upload-artifact` / `actions/download-artifact`.

### Jenkins

Defined in `Jenkinsfile`. Uses a Kubernetes pod template with four containers:
- `gradle` — Gradle 8.5 with JDK 17
- `python` — Python 3.11 with BDD dependencies
- `helm` — Helm 3.14 for deployment and chart packaging
- `security` — Syft + Grype for security scanning

**Stages:**
1. Fetch Cameo Model
2. Traceability Check
3. Run Simulations (live K8s deployment)
4. BDD Log Analysis
5. Traceability Report (with HTML publish)
6. Security Scan
7. Package and Publish (main branch only)

All container images are pulled from the internal registry (`registry.internal.example.com`). Credentials for Nexus and the Kubernetes cluster are injected via Jenkins credentials.

Pipeline timeout: 60 minutes. Build history retained for 30 builds.

---

## INCOSE Verification Criteria

The pipeline supports all four INCOSE verification criteria. Each requirement in the Cameo model specifies its verification method, which determines how it is handled:

| Method | Tag | Handling |
|--------|-----|----------|
| **Test** | `@VER:Test` | Fully automated. BDD scenarios execute log analysis assertions against simulation output. |
| **Demonstration** | `@VER:Demonstration` | Automated stubs generated. May require manual execution depending on the specific demonstration procedure. |
| **Analysis** | `@VER:Analysis` | Tagged `@manual`. Stub generated in `bdd/features/non_test/`. Skipped by automated pipeline; requires human review of analytical evidence. |
| **Inspection** | `@VER:Inspection` | Tagged `@manual`. Stub generated in `bdd/features/non_test/`. Skipped by automated pipeline; requires human inspection and sign-off. |

Non-Test methods (Analysis, Demonstration, Inspection) are separated into `bdd/features/non_test/` and tagged `@manual` so they are tracked for traceability coverage but do not block the automated pipeline.

---

## Air-Gapped Environment Notes

This pipeline is designed to operate in disconnected (air-gapped) environments common in DoD and NIST-compliant deployments:

- **Internal Nexus only.** The Gradle build configuration (`build.gradle`) points exclusively to an internal Nexus repository. No external Maven Central or public registry access is required. The `allowInsecureProtocol` flag is set to `false`.
- **Internal container registry.** All container images (product, simulator, tooling) are pulled from `registry.internal.example.com`. Helm chart values reference this registry by default.
- **Local cosign keys.** Artifact signing uses local key pairs instead of Fulcio/Rekor (which require internet connectivity to the Sigstore transparency log).
- **Vendored tooling.** Jenkins pod agents use pre-built tool images from the internal registry containing Gradle, Python, Helm, Syft, and Grype.
- **No external vulnerability databases at scan time.** Grype databases must be pre-loaded or mirrored internally.
- **SLSA provenance** is generated locally without reliance on external attestation services.

To configure for your environment, set these variables:
```bash
export NEXUS_URL=https://your-nexus.internal/repository/maven-releases/
export NEXUS_USER=<service-account>
export NEXUS_PASS=<password>
export REGISTRY=your-registry.internal
export KUBECONFIG=/path/to/kubeconfig
export COSIGN_KEY=/path/to/cosign.key
export COSIGN_PASSWORD=<key-password>
```

---

## Upstream: cameo-model-pipeline

This repository consumes artifacts produced by the **cameo-model-pipeline** repository. The upstream pipeline:

1. Exports requirements, ICD definitions, and protobuf schemas from a MagicDraw/Cameo SysML model.
2. Packages the export as a versioned zip artifact (`com.org.systems:cameo-model-artifacts:<version>`).
3. Publishes the zip to the internal Nexus repository.

This product-pipeline then:

1. Fetches the published zip via Gradle dependency resolution (`configurations.cameoModel`).
2. Unpacks it to `build/cameo/`, which contains:
   - `requirements/requirements.json` — structured requirements with IDs, titles, descriptions, verification criteria, and verification criteria.
   - `proto/` — protobuf definitions for ICD message schemas.
3. Runs traceability gates against the extracted requirements.

When the Cameo model is updated upstream, bump `cameo.version` in `versions.properties` to pull in the new export:
```properties
cameo.version=0.2.0
```

---

## Contributing

### Adding a New BDD Scenario

1. Create or edit a `.feature` file in `bdd/features/automated/`.
2. Tag it with `@REQ:<requirement-id>` linking to the Cameo requirement.
3. Add `@VER:<method>` to declare the verification criteria.
4. Implement step definitions in `bdd/features/steps/`. Steps must perform pure log file assertions -- no network calls.
5. Run the traceability checker locally to verify coverage.

### Updating After a Cameo Model Change

1. Bump `cameo.version` in `versions.properties`.
2. Run `./gradlew unpackCameoZip` to fetch the new model.
3. Run the traceability checker. If Gate B detects drift:
   - Review the changed verification criteria.
   - Update affected BDD scenarios as needed.
   - Remove any `@REVIEW_REQUIRED` tags.
   - Run with `--update-baseline` to reset the baseline.
4. If Gate A finds uncovered requirements, replace the generated stubs with real scenarios.

### Updating Container Versions

1. Edit `versions.properties` with the new image tags.
2. Update `helm/product-chart/values.yaml` to match.
3. Run the pipeline to verify deployment and security scans pass.

### Branch and PR Workflow

- All changes go through pull requests to `main`.
- The GitHub Actions workflow runs on every PR: traceability check, BDD analysis, and report generation.
- Helm chart packaging and publishing only occur on the `main` branch.
- Jenkins runs the full pipeline including live K8s simulation and security scans.

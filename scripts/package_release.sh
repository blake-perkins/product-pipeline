#!/usr/bin/env bash
set -euo pipefail

# package_release.sh
#
# Assembles the final release bundle containing:
# - Helm chart (.tgz)
# - Auto-generated documentation (API ref, requirements doc, traceability matrix)
# - Manually authored documentation
# - Security artifacts (SBOM, vulnerability report)
# - Test results
# - Release notes and manifest

BUILD_DIR="${1:-build}"
DOCS_DIR="${2:-docs}"
VERSION=$(grep helm.chart.version versions.properties | cut -d= -f2)
RELEASE_NAME="product-release-${VERSION}"
RELEASE_DIR="${BUILD_DIR}/release/${RELEASE_NAME}"

echo "============================================"
echo " Packaging Release Bundle"
echo " Version: ${VERSION}"
echo "============================================"

# Create release directory structure
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"/{helm,docs,security,test-results}

# ─── Helm Chart ───
if [ -d "${BUILD_DIR}/helm" ]; then
    cp "${BUILD_DIR}"/helm/*.tgz "$RELEASE_DIR/helm/" 2>/dev/null || \
        echo "WARNING: No Helm chart found in ${BUILD_DIR}/helm/"
fi

# ─── Auto-Generated Docs ───
# Traceability matrix
if [ -f "${BUILD_DIR}/reports/traceability/traceability_report.html" ]; then
    cp "${BUILD_DIR}/reports/traceability/traceability_report.html" \
        "$RELEASE_DIR/docs/traceability-matrix.html"
fi

# Requirements document (if generated)
if [ -f "${BUILD_DIR}/docs/requirements-document.html" ]; then
    cp "${BUILD_DIR}/docs/requirements-document.html" "$RELEASE_DIR/docs/"
fi

# API reference (if generated from proto)
if [ -f "${BUILD_DIR}/docs/api-reference.html" ]; then
    cp "${BUILD_DIR}/docs/api-reference.html" "$RELEASE_DIR/docs/"
fi

# ─── Manually Authored Docs ───
for doc_dir in user-guide installation-guide; do
    if [ -d "${DOCS_DIR}/${doc_dir}" ]; then
        # Convert markdown to HTML if pandoc is available
        for md_file in "${DOCS_DIR}/${doc_dir}"/*.md; do
            if [ -f "$md_file" ]; then
                basename=$(basename "$md_file" .md)
                if command -v pandoc &> /dev/null; then
                    pandoc "$md_file" -o "$RELEASE_DIR/docs/${basename}.html" \
                        --standalone --metadata title="${basename}" 2>/dev/null || \
                        cp "$md_file" "$RELEASE_DIR/docs/"
                else
                    cp "$md_file" "$RELEASE_DIR/docs/"
                fi
            fi
        done
    fi
done

# ─── Security Artifacts ───
if [ -f "${BUILD_DIR}/reports/security/sbom.json" ]; then
    cp "${BUILD_DIR}/reports/security/sbom.json" "$RELEASE_DIR/security/"
fi
if [ -f "${BUILD_DIR}/reports/security/grype-results.json" ]; then
    cp "${BUILD_DIR}/reports/security/grype-results.json" \
        "$RELEASE_DIR/security/vulnerability-report.json"
fi

# ─── Test Results ───
if [ -f "${BUILD_DIR}/reports/bdd/behave-results.json" ]; then
    cp "${BUILD_DIR}/reports/bdd/behave-results.json" "$RELEASE_DIR/test-results/"
fi

# ─── Release Notes ───
if [ -f "${DOCS_DIR}/release-notes/release-notes.md" ]; then
    cp "${DOCS_DIR}/release-notes/release-notes.md" "$RELEASE_DIR/"
fi

# ─── Manifest ───
python3 -c "
import json, hashlib, os
from datetime import datetime, timezone

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

manifest = {
    'version': '${VERSION}',
    'buildTimestamp': datetime.now(timezone.utc).isoformat(),
    'gitCommitSha': os.environ.get('GIT_COMMIT', os.environ.get('GITHUB_SHA', 'unknown')),
    'gitBranch': os.environ.get('GIT_BRANCH', os.environ.get('GITHUB_REF_NAME', 'unknown')),
    'contents': {}
}

release_dir = '${RELEASE_DIR}'
for root, dirs, files in os.walk(release_dir):
    for f in files:
        fpath = os.path.join(root, f)
        rel = os.path.relpath(fpath, release_dir)
        manifest['contents'][rel] = {
            'sha256': sha256_file(fpath),
            'size_bytes': os.path.getsize(fpath)
        }

with open(os.path.join(release_dir, 'manifest.json'), 'w') as f:
    json.dump(manifest, f, indent=2)
"

# ─── Create ZIP ───
cd "${BUILD_DIR}/release"
zip -r "../${RELEASE_NAME}.zip" "${RELEASE_NAME}/"
echo ""
echo "Release bundle created: ${BUILD_DIR}/${RELEASE_NAME}.zip"
echo "Contents:"
unzip -l "${BUILD_DIR}/../${BUILD_DIR}/${RELEASE_NAME}.zip" 2>/dev/null || \
    ls -la "${RELEASE_DIR}/"

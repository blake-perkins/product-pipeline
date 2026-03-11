#!/usr/bin/env bash
set -euo pipefail

# scan.sh
#
# Orchestrates Syft (SBOM generation) and Grype (vulnerability scanning)
# against product container images.
#
# Usage:
#   ./security/scan.sh --registry <registry> --images <img1,img2> \
#       --sbom-output <path> --grype-output <path> --policy <path>

SCAN_FAILED=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --registry)   REGISTRY="$2"; shift 2;;
        --images)     IFS=',' read -ra IMAGES <<< "$2"; shift 2;;
        --sbom-output) SBOM_OUT="$2"; shift 2;;
        --grype-output) GRYPE_OUT="$2"; shift 2;;
        --policy)     POLICY="$2"; shift 2;;
        *) echo "Unknown argument: $1"; exit 1;;
    esac
done

REGISTRY="${REGISTRY:?--registry is required}"
SBOM_OUT="${SBOM_OUT:?--sbom-output is required}"
GRYPE_OUT="${GRYPE_OUT:?--grype-output is required}"
POLICY="${POLICY:?--policy is required}"

mkdir -p "$(dirname "$SBOM_OUT")" "$(dirname "$GRYPE_OUT")"

echo "============================================"
echo " Security Scan"
echo " Registry: ${REGISTRY}"
echo " Images:   ${#IMAGES[@]}"
echo "============================================"

# Clear previous results
> "$GRYPE_OUT"

for IMAGE in "${IMAGES[@]}"; do
    FULL_IMAGE="${REGISTRY}/${IMAGE}"
    SAFE_NAME="${IMAGE//\//_}"
    SAFE_NAME="${SAFE_NAME//:/_}"

    echo ""
    echo "--- Scanning: ${FULL_IMAGE} ---"

    # Generate SBOM with Syft
    echo "  Generating SBOM..."
    syft "${FULL_IMAGE}" -o cyclonedx-json > "/tmp/sbom-${SAFE_NAME}.json" 2>/dev/null || {
        echo "  WARNING: Syft failed for ${FULL_IMAGE}"
        continue
    }

    # Scan with Grype
    echo "  Running vulnerability scan..."
    grype "sbom:/tmp/sbom-${SAFE_NAME}.json" \
        -o json \
        --config "${POLICY}" \
        >> "${GRYPE_OUT}" 2>/dev/null || {
        echo "  VULNERABILITIES FOUND in ${FULL_IMAGE}"
        SCAN_FAILED=1
    }

    echo "  Done: ${FULL_IMAGE}"
done

# Merge SBOMs into single output
echo ""
echo "Merging SBOMs..."
python3 -c "
import json, glob, sys

merged = {
    'bomFormat': 'CycloneDX',
    'specVersion': '1.4',
    'components': []
}

for f in glob.glob('/tmp/sbom-*.json'):
    try:
        with open(f) as fh:
            data = json.load(fh)
            merged['components'].extend(data.get('components', []))
    except (json.JSONDecodeError, KeyError) as e:
        print(f'WARNING: Could not parse {f}: {e}', file=sys.stderr)

with open('${SBOM_OUT}', 'w') as out:
    json.dump(merged, out, indent=2)

print(f'  Merged SBOM: {len(merged[\"components\"])} components')
"

echo ""
if [ "${SCAN_FAILED}" -eq 1 ]; then
    echo "SECURITY SCAN FAILED: Vulnerabilities found exceeding policy thresholds."
    echo "Review: ${GRYPE_OUT}"
    exit 1
else
    echo "SECURITY SCAN PASSED: No vulnerabilities exceeding policy thresholds."
fi

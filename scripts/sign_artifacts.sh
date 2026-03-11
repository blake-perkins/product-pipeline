#!/usr/bin/env bash
set -euo pipefail

# sign_artifacts.sh
#
# Signs release artifacts using cosign for supply chain security.
# In air-gapped environments, uses a local key pair (not Fulcio/Rekor).
#
# Usage:
#   ./scripts/sign_artifacts.sh <release_zip_path> [--key <cosign_key_path>]
#
# Environment variables:
#   COSIGN_KEY      - Path to cosign private key (default: cosign.key)
#   COSIGN_PASSWORD - Password for the cosign key
#   REGISTRY        - Container registry for image signing

RELEASE_ZIP="${1:?Usage: sign_artifacts.sh <release_zip_path> [--key <key_path>]}"
shift

COSIGN_KEY="${COSIGN_KEY:-cosign.key}"

while [[ $# -gt 0 ]]; do
    case $1 in
        --key) COSIGN_KEY="$2"; shift 2;;
        *) shift;;
    esac
done

if ! command -v cosign &> /dev/null; then
    echo "WARNING: cosign not found. Skipping artifact signing."
    echo "Install cosign for artifact signing: https://docs.sigstore.dev/cosign/installation/"
    exit 0
fi

if [ ! -f "$COSIGN_KEY" ]; then
    echo "WARNING: Cosign key not found at ${COSIGN_KEY}. Skipping signing."
    echo "Generate a key pair: cosign generate-key-pair"
    exit 0
fi

echo "============================================"
echo " Signing Artifacts"
echo " Release: ${RELEASE_ZIP}"
echo " Key:     ${COSIGN_KEY}"
echo "============================================"

# Sign the release bundle
echo ""
echo "--- Signing release bundle ---"
cosign sign-blob \
    --key "$COSIGN_KEY" \
    --output-signature "${RELEASE_ZIP}.sig" \
    "$RELEASE_ZIP"
echo "  Signature: ${RELEASE_ZIP}.sig"

# Verify the signature
echo ""
echo "--- Verifying signature ---"
cosign verify-blob \
    --key "${COSIGN_KEY%.key}.pub" \
    --signature "${RELEASE_ZIP}.sig" \
    "$RELEASE_ZIP"
echo "  Verification: PASSED"

# Sign container images (if registry is configured)
REGISTRY="${REGISTRY:-}"
if [ -n "$REGISTRY" ] && [ -f versions.properties ]; then
    echo ""
    echo "--- Signing container images ---"

    TOPOLOGY=$(grep deploy.topology versions.properties | cut -d= -f2)
    if [ "$TOPOLOGY" = "single" ]; then
        IMAGE="${REGISTRY}/$(grep single.container.image versions.properties | cut -d= -f2):$(grep single.container.version versions.properties | cut -d= -f2)"
        cosign sign --key "$COSIGN_KEY" "$IMAGE" 2>/dev/null && \
            echo "  Signed: $IMAGE" || echo "  WARNING: Could not sign $IMAGE"
    else
        for prefix in container.a container.b sidecar; do
            IMG=$(grep "${prefix}.image" versions.properties | cut -d= -f2)
            VER=$(grep "${prefix}.version" versions.properties | cut -d= -f2)
            FULL="${REGISTRY}/${IMG}:${VER}"
            cosign sign --key "$COSIGN_KEY" "$FULL" 2>/dev/null && \
                echo "  Signed: $FULL" || echo "  WARNING: Could not sign $FULL"
        done
    fi
fi

echo ""
echo "Artifact signing complete."

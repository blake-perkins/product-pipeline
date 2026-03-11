#!/usr/bin/env bash
set -euo pipefail

##############################################################################
# generate_provenance.sh
#
# Generates a SLSA v0.2 provenance attestation (in-toto Statement v0.1)
# for a release bundle zip file.
#
# Usage:
#   ./scripts/generate_provenance.sh <release_zip_path> <output_path>
##############################################################################

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <release_zip_path> <output_path>" >&2
  exit 1
fi

RELEASE_ZIP="$1"
OUTPUT_PATH="$2"

if [[ ! -f "$RELEASE_ZIP" ]]; then
  echo "Error: release zip not found: $RELEASE_ZIP" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Compute sha256 digest of the release zip
# ---------------------------------------------------------------------------
compute_sha256() {
  if command -v sha256sum &>/dev/null; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum &>/dev/null; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    echo "Error: neither sha256sum nor shasum found" >&2
    exit 1
  fi
}

ZIP_SHA256="$(compute_sha256 "$RELEASE_ZIP")"
ZIP_NAME="$(basename "$RELEASE_ZIP")"

# ---------------------------------------------------------------------------
# Git context
# ---------------------------------------------------------------------------
GIT_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo "unknown")"
GIT_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
GIT_REMOTE_URL="$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || echo "unknown")"

# ---------------------------------------------------------------------------
# Read versions.properties
# ---------------------------------------------------------------------------
VERSIONS_FILE="$REPO_ROOT/versions.properties"

read_prop() {
  local key="$1"
  if [[ -f "$VERSIONS_FILE" ]]; then
    grep "^${key}=" "$VERSIONS_FILE" 2>/dev/null | head -1 | cut -d'=' -f2-
  fi
}

CAMEO_VERSION="$(read_prop 'cameo.version')"
CAMEO_VERSION="${CAMEO_VERSION:-unknown}"

CONTAINER_A_IMAGE="$(read_prop 'container.a.image')"
CONTAINER_A_IMAGE="${CONTAINER_A_IMAGE:-unknown}"
CONTAINER_A_VERSION="$(read_prop 'container.a.version')"
CONTAINER_A_VERSION="${CONTAINER_A_VERSION:-unknown}"

CONTAINER_B_IMAGE="$(read_prop 'container.b.image')"
CONTAINER_B_IMAGE="${CONTAINER_B_IMAGE:-unknown}"
CONTAINER_B_VERSION="$(read_prop 'container.b.version')"
CONTAINER_B_VERSION="${CONTAINER_B_VERSION:-unknown}"

SIDECAR_IMAGE="$(read_prop 'sidecar.image')"
SIDECAR_IMAGE="${SIDECAR_IMAGE:-unknown}"
SIDECAR_VERSION="$(read_prop 'sidecar.version')"
SIDECAR_VERSION="${SIDECAR_VERSION:-unknown}"

# ---------------------------------------------------------------------------
# Build environment
# ---------------------------------------------------------------------------
if [[ -n "${BUILD_URL:-}" ]]; then
  BUILDER_ID="$BUILD_URL"
elif [[ -n "${GITHUB_RUN_ID:-}" ]]; then
  BUILDER_ID="https://github.com/actions/runs/${GITHUB_RUN_ID}"
else
  BUILDER_ID="local"
fi

BUILD_NUM="${BUILD_NUMBER:-unknown}"
BUILD_TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# ---------------------------------------------------------------------------
# Generate provenance JSON via python3 (ensures valid JSON output)
# ---------------------------------------------------------------------------
python3 -c "
import json, sys

provenance = {
    '_type': 'https://in-toto.io/Statement/v0.1',
    'predicateType': 'https://slsa.dev/provenance/v0.2',
    'subject': [
        {
            'name': sys.argv[1],
            'digest': {'sha256': sys.argv[2]}
        }
    ],
    'predicate': {
        'builder': {'id': sys.argv[3]},
        'buildType': 'https://internal/pipeline/v1',
        'invocation': {
            'configSource': {
                'uri': sys.argv[4] + '@' + sys.argv[5],
                'digest': {'sha1': sys.argv[6]},
                'entryPoint': 'Jenkinsfile'
            }
        },
        'materials': [
            {'uri': 'nexus://cameo-model-artifacts:' + sys.argv[7], 'digest': {}},
            {'uri': 'registry://' + sys.argv[8] + ':' + sys.argv[9], 'digest': {}},
            {'uri': 'registry://' + sys.argv[10] + ':' + sys.argv[11], 'digest': {}},
            {'uri': 'registry://' + sys.argv[12] + ':' + sys.argv[13], 'digest': {}}
        ],
        'metadata': {
            'buildStartedOn': sys.argv[14],
            'buildNumber': sys.argv[15],
            'completeness': {
                'parameters': False,
                'environment': False,
                'materials': True
            }
        }
    }
}

with open(sys.argv[16], 'w') as f:
    json.dump(provenance, f, indent=2)
" \
  "$ZIP_NAME" \
  "$ZIP_SHA256" \
  "$BUILDER_ID" \
  "$GIT_REMOTE_URL" \
  "$GIT_BRANCH" \
  "$GIT_COMMIT" \
  "$CAMEO_VERSION" \
  "$CONTAINER_A_IMAGE" \
  "$CONTAINER_A_VERSION" \
  "$CONTAINER_B_IMAGE" \
  "$CONTAINER_B_VERSION" \
  "$SIDECAR_IMAGE" \
  "$SIDECAR_VERSION" \
  "$BUILD_TIMESTAMP" \
  "$BUILD_NUM" \
  "$OUTPUT_PATH"

echo "Provenance attestation written to: $OUTPUT_PATH"

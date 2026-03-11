#!/usr/bin/env bash
set -euo pipefail

# run_simulations.sh
#
# Orchestrates the full simulation lifecycle:
# 1. Deploy product (single container or full pod)
# 2. Deploy simulator
# 3. Wait for simulations to complete
# 4. Collect logs from all pods
# 5. Tear down simulator and product
#
# Called by Jenkins/GitHub Actions, NOT by Behave.
# Behave only reads the collected logs from $LOG_OUTPUT_DIR.
#
# Usage:
#   ./scripts/run_simulations.sh <namespace> <log_output_dir> <topology> <timeout_seconds>

NAMESPACE="${1:-test}"
LOG_OUTPUT_DIR="${2:-build/logs}"
TOPOLOGY="${3:-pod}"
TIMEOUT="${4:-300}"

echo "============================================"
echo " Simulation Runner"
echo " Namespace: ${NAMESPACE}"
echo " Topology:  ${TOPOLOGY}"
echo " Timeout:   ${TIMEOUT}s"
echo "============================================"

# ─── Step 1: Deploy Product ───
echo ""
echo "=== [1/5] Deploying product (topology: ${TOPOLOGY}) ==="
if [ "$TOPOLOGY" = "single" ]; then
    helm upgrade --install product-under-test helm/single-container-chart \
        --namespace "$NAMESPACE" \
        --create-namespace \
        --wait --timeout 5m
else
    helm upgrade --install product-under-test helm/product-chart \
        --namespace "$NAMESPACE" \
        --create-namespace \
        --wait --timeout 5m
fi
echo "Product deployed successfully."

# ─── Step 2: Deploy Simulator ───
echo ""
echo "=== [2/5] Deploying simulator ==="
helm upgrade --install simulator helm/simulator-chart \
    --namespace "$NAMESPACE" \
    --set productEndpoint="product-under-test:50051" \
    --set completionTimeout="$TIMEOUT" \
    --wait --timeout 3m
echo "Simulator deployed successfully."

# ─── Step 3: Wait for Simulations ───
echo ""
echo "=== [3/5] Waiting for simulations to complete (timeout: ${TIMEOUT}s) ==="
SIMULATION_FAILED=0
kubectl wait --for=condition=complete job/simulator-job \
    --namespace "$NAMESPACE" \
    --timeout="${TIMEOUT}s" || {
    echo "WARNING: Simulations did not complete within ${TIMEOUT}s"
    SIMULATION_FAILED=1
}

# ─── Step 4: Collect Logs ───
echo ""
echo "=== [4/5] Collecting logs ==="
mkdir -p "$LOG_OUTPUT_DIR/product" "$LOG_OUTPUT_DIR/simulator"

# Collect product container logs
PRODUCT_POD=$(kubectl get pod -l app=product -n "$NAMESPACE" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$PRODUCT_POD" ]; then
    for CONTAINER in $(kubectl get pod "$PRODUCT_POD" -n "$NAMESPACE" \
        -o jsonpath='{.spec.containers[*].name}'); do
        echo "  Collecting logs: ${PRODUCT_POD}/${CONTAINER}"
        kubectl logs "$PRODUCT_POD" -n "$NAMESPACE" -c "$CONTAINER" \
            > "$LOG_OUTPUT_DIR/product/${CONTAINER}.log" 2>&1 || true
    done
else
    echo "WARNING: No product pod found. Skipping product log collection."
fi

# Collect simulator logs
SIMULATOR_POD=$(kubectl get pod -l app=simulator -n "$NAMESPACE" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$SIMULATOR_POD" ]; then
    echo "  Collecting logs: ${SIMULATOR_POD}"
    kubectl logs "$SIMULATOR_POD" -n "$NAMESPACE" \
        > "$LOG_OUTPUT_DIR/simulator/simulator.log" 2>&1 || true
else
    echo "WARNING: No simulator pod found. Skipping simulator log collection."
fi

# Write run metadata
RESTART_COUNT=0
FINAL_STATUS="Unknown"
if [ -n "$PRODUCT_POD" ]; then
    RESTART_COUNT=$(kubectl get pod "$PRODUCT_POD" -n "$NAMESPACE" \
        -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo "0")
    POD_PHASE=$(kubectl get pod "$PRODUCT_POD" -n "$NAMESPACE" \
        -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
    FINAL_STATUS="$POD_PHASE"
fi

python3 -c "
import json
from datetime import datetime, timezone
metadata = {
    'simulation_timestamp': datetime.now(timezone.utc).isoformat(),
    'namespace': '${NAMESPACE}',
    'topology': '${TOPOLOGY}',
    'timeout_seconds': ${TIMEOUT},
    'simulation_completed': ${SIMULATION_FAILED} == 0,
    'product_restart_count': int('${RESTART_COUNT}' or '0'),
    'product_final_status': '${FINAL_STATUS}',
}
with open('${LOG_OUTPUT_DIR}/metadata.json', 'w') as f:
    json.dump(metadata, f, indent=2)
print('  Metadata written to ${LOG_OUTPUT_DIR}/metadata.json')
"

echo ""
echo "  Log files:"
find "$LOG_OUTPUT_DIR" -type f | while read -r f; do echo "    $f"; done

# ─── Step 5: Teardown ───
echo ""
echo "=== [5/5] Tearing down ==="
helm uninstall simulator --namespace "$NAMESPACE" 2>/dev/null || true
helm uninstall product-under-test --namespace "$NAMESPACE" 2>/dev/null || true
echo "Teardown complete."

echo ""
echo "============================================"
echo " Simulation complete. Logs: $LOG_OUTPUT_DIR"
echo "============================================"

if [ "$SIMULATION_FAILED" -eq 1 ]; then
    echo "WARNING: Simulations did not complete successfully."
    # Don't exit 1 here — let Behave analyze whatever logs were collected
fi

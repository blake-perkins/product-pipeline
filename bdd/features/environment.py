"""
Behave environment hooks for BDD log analysis.

Loads simulation logs from disk at startup. Behave steps only read
these pre-collected log files — NO network calls, NO kubectl, NO
container interaction.
"""
import json
import os
from pathlib import Path


LOG_DIR = os.environ.get("LOG_DIR", "build/logs")


def before_all(context):
    """Load all log files and run metadata into context."""
    context.log_dir = LOG_DIR

    # Load run metadata
    metadata_path = os.path.join(LOG_DIR, "metadata.json")
    if os.path.exists(metadata_path):
        with open(metadata_path, encoding="utf-8") as f:
            context.run_metadata = json.load(f)
    else:
        context.run_metadata = {}

    # Load product logs (all container log files)
    context.product_logs = {}
    product_dir = os.path.join(LOG_DIR, "product")
    if os.path.isdir(product_dir):
        for fname in sorted(os.listdir(product_dir)):
            if fname.endswith(".log"):
                fpath = os.path.join(product_dir, fname)
                with open(fpath, encoding="utf-8") as f:
                    context.product_logs[fname] = f.read()

    # Load simulator logs
    sim_log = os.path.join(LOG_DIR, "simulator", "simulator.log")
    if os.path.exists(sim_log):
        with open(sim_log, encoding="utf-8") as f:
            context.simulator_logs = f.read()
    else:
        context.simulator_logs = ""

    # Parse structured log entries for timing analysis
    context.product_log_entries = {}
    for fname, content in context.product_logs.items():
        entries = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                entries.append({"raw": line})
        context.product_log_entries[fname] = entries


def before_scenario(context, scenario):
    """Handle topology-based scenario skipping and manual tags."""
    # Skip scenarios tagged @manual
    if "manual" in scenario.effective_tags:
        scenario.skip("Manual verification — not run in automated pipeline")
        return

    # Skip scenarios for non-matching topology
    topology = os.environ.get("DEPLOY_TOPOLOGY", "pod")
    topology_tags = [t for t in scenario.effective_tags if t.startswith("topology:")]
    if topology_tags and f"topology:{topology}" not in scenario.effective_tags:
        scenario.skip(f"Skipped: requires different topology than '{topology}'")

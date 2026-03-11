"""
Log analysis Behave step definitions.

Pure assertions on log files loaded from disk. No network calls,
no kubectl, no container interaction.
"""
import json
from datetime import datetime
from behave import given, then


def _all_product_logs(context) -> str:
    """Concatenate all product log files into a single string."""
    return "\n".join(context.product_logs.values())


def _all_product_entries(context) -> list[dict]:
    """Get all parsed structured log entries across all product log files."""
    entries = []
    for file_entries in context.product_log_entries.values():
        entries.extend(file_entries)
    return entries


def _parse_timestamp(ts_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string."""
    # Handle both with and without 'Z' suffix
    ts_str = ts_str.replace("Z", "+00:00")
    return datetime.fromisoformat(ts_str)


# ─── Log Content Assertions ───

@then('the product logs should contain "{expected_text}"')
def step_check_product_logs(context, expected_text):
    """Search all product log files for the expected text."""
    all_logs = _all_product_logs(context)
    assert expected_text in all_logs, (
        f"Expected '{expected_text}' not found in product logs"
    )


@then('the product logs should not contain "{unexpected_text}"')
def step_check_product_logs_absent(context, unexpected_text):
    """Verify text is NOT present in product logs."""
    all_logs = _all_product_logs(context)
    assert unexpected_text not in all_logs, (
        f"Unexpected text '{unexpected_text}' found in product logs"
    )


@then('the simulator logs should confirm "{expected_text}"')
def step_check_simulator_logs(context, expected_text):
    """Search simulator logs for confirmation text."""
    assert context.simulator_logs, "No simulator logs found"
    assert expected_text in context.simulator_logs, (
        f"Expected '{expected_text}' not found in simulator logs"
    )


# ─── Timing Assertions ───

@then(
    'the product logs should contain "{text}" '
    'within {threshold:d}ms of the request'
)
def step_check_timing(context, text, threshold):
    """Parse structured JSON logs and verify timing between correlated events."""
    entries = _all_product_entries(context)

    # Find the first entry containing the text
    target_entry = None
    for entry in entries:
        msg = entry.get("message", entry.get("raw", ""))
        if text in str(msg):
            target_entry = entry
            break

    assert target_entry is not None, (
        f"No log entry containing '{text}' found"
    )

    # Find the corresponding request entry (look for the most recent entry before it)
    if "request_id" in target_entry:
        req_id = target_entry["request_id"]
        request_entry = None
        for entry in entries:
            if (
                entry.get("request_id") == req_id
                and entry is not target_entry
                and "timestamp" in entry
            ):
                request_entry = entry
                break

        if request_entry and "timestamp" in target_entry:
            req_ts = _parse_timestamp(request_entry["timestamp"])
            resp_ts = _parse_timestamp(target_entry["timestamp"])
            delta_ms = (resp_ts - req_ts).total_seconds() * 1000
            assert delta_ms <= threshold, (
                f"Response took {delta_ms:.1f}ms, exceeds threshold of {threshold}ms"
            )


@then(
    "every IcdResponse should occur within {threshold:d}ms "
    "of its corresponding IcdRequest"
)
def step_check_all_response_times(context, threshold):
    """Pair all request/response log entries by request_id, verify timing."""
    entries = _all_product_entries(context)

    requests = {}
    responses = {}
    for entry in entries:
        msg = entry.get("message", "")
        req_id = entry.get("request_id")
        ts = entry.get("timestamp")
        if not req_id or not ts:
            continue
        if "IcdRequest" in str(msg) or "Received" in str(msg):
            requests[req_id] = _parse_timestamp(ts)
        elif "IcdResponse" in str(msg) or "Sent" in str(msg):
            responses[req_id] = _parse_timestamp(ts)

    assert requests, "No IcdRequest entries found in logs"

    violations = []
    for req_id, req_ts in requests.items():
        if req_id in responses:
            delta_ms = (responses[req_id] - req_ts).total_seconds() * 1000
            if delta_ms > threshold:
                violations.append(
                    f"  {req_id}: {delta_ms:.1f}ms (threshold: {threshold}ms)"
                )

    assert not violations, (
        f"{len(violations)} response(s) exceeded {threshold}ms threshold:\n"
        + "\n".join(violations)
    )


@then("the average response time should be less than {threshold:d}ms")
def step_avg_response_time(context, threshold):
    """Calculate average response time from paired request/response entries."""
    entries = _all_product_entries(context)

    requests = {}
    responses = {}
    for entry in entries:
        msg = entry.get("message", "")
        req_id = entry.get("request_id")
        ts = entry.get("timestamp")
        if not req_id or not ts:
            continue
        if "Request" in str(msg):
            requests[req_id] = _parse_timestamp(ts)
        elif "Response" in str(msg):
            responses[req_id] = _parse_timestamp(ts)

    deltas = []
    for req_id in requests:
        if req_id in responses:
            delta_ms = (responses[req_id] - requests[req_id]).total_seconds() * 1000
            deltas.append(delta_ms)

    assert deltas, "No matched request/response pairs found for timing analysis"

    avg_ms = sum(deltas) / len(deltas)
    assert avg_ms < threshold, (
        f"Average response time {avg_ms:.1f}ms exceeds threshold of {threshold}ms "
        f"(based on {len(deltas)} pairs)"
    )


# ─── Error Assertions ───

@then("no error entries should appear in the product logs")
def step_no_errors(context):
    """Verify no ERROR-level entries in any product log file."""
    error_lines = []
    for fname, content in context.product_logs.items():
        for i, line in enumerate(content.splitlines(), 1):
            try:
                entry = json.loads(line)
                level = entry.get("level", "")
                if level in ("ERROR", "FATAL", "PANIC"):
                    error_lines.append(
                        f"  {fname}:{i}: [{level}] {entry.get('message', line.strip())}"
                    )
            except json.JSONDecodeError:
                if "ERROR" in line or "PANIC" in line or "FATAL" in line:
                    error_lines.append(f"  {fname}:{i}: {line.strip()}")

    assert not error_lines, (
        f"Found {len(error_lines)} error(s) in product logs:\n"
        + "\n".join(error_lines)
    )


@then("no ERROR or PANIC entries should appear in the product logs")
def step_no_errors_or_panics(context):
    """Alias for no error entries check."""
    step_no_errors(context)


@then("no crash or panic entries should appear in the product logs")
def step_no_crashes(context):
    """Verify no crash/panic entries in logs."""
    all_logs = _all_product_logs(context)
    panic_indicators = ["PANIC", "SIGSEGV", "core dumped", "Segmentation fault"]
    found = [ind for ind in panic_indicators if ind in all_logs]
    assert not found, f"Crash indicators found in product logs: {found}"


# ─── Health Assertions ───

@then("the product should not have restarted during the simulation")
def step_no_restart(context):
    """Check run metadata for restart count."""
    restarts = context.run_metadata.get("product_restart_count", 0)
    assert restarts == 0, (
        f"Product restarted {restarts} time(s) during simulation"
    )


@then("the product should remain healthy after the run")
def step_still_healthy(context):
    """Check metadata indicates healthy final state."""
    final_status = context.run_metadata.get("product_final_status", "unknown")
    assert final_status != "Failed", (
        f"Product was not healthy after simulation. Status: {final_status}"
    )

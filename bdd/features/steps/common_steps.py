"""
Common Behave step definitions.

Includes the stub-failure step that causes auto-generated stub scenarios
to fail the pipeline with NotImplementedError.
"""
from behave import given, when, then


@given("the simulation logs are loaded")
def step_load_logs(context):
    """Verify logs were loaded by environment.py and are non-empty."""
    assert context.product_logs, (
        "No product logs found. "
        "Ensure simulations ran and logs were collected to build/logs/product/"
    )


@given("the simulation logs are loaded for \"{simulation_name}\"")
def step_load_logs_for_sim(context, simulation_name):
    """Verify logs exist for a specific simulation."""
    assert context.product_logs, (
        f"No product logs found for simulation '{simulation_name}'. "
        "Ensure simulations ran and logs were collected to build/logs/product/"
    )
    context.current_simulation = simulation_name


@given("the system is deployed")
def step_system_deployed(context):
    """Placeholder for stubs — logs are loaded in environment.py."""
    pass


@given("verification evidence is documented")
def step_evidence_documented(context):
    """Placeholder for manual verification scenarios."""
    pass


# ─── Stub Steps (Auto-Generated Scenarios) ───

@given('the system is configured for {method} verification of "{req_id}"')
def step_configured_for_verification(context, method, req_id):
    """Placeholder step for auto-generated stubs."""
    context.verification_method = method
    context.verification_req_id = req_id


@when("the {method} verification is performed")
def step_verification_performed(context, method):
    """Placeholder step for auto-generated stubs."""
    pass


@given("the scenario is executed")
def step_scenario_executed(context):
    """Placeholder step for auto-generated stubs."""
    pass


@then("it should fail because it is not yet implemented")
def step_not_implemented(context):
    """This step always fails — it exists only in auto-generated stubs."""
    raise NotImplementedError(
        "This scenario is an auto-generated stub. "
        "Implement the actual test to satisfy the linked requirement. "
        "Remove the @STUB and @AUTO_GENERATED tags when done."
    )


@then("the analysis report is attached to the verification record")
def step_analysis_report_attached(context):
    """Placeholder for manual Analysis verification."""
    pass

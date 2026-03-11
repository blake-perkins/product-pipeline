@REQ:SYS-REQ-001 @VER:Test
Feature: Basic ICD Communications
  Verify that the product correctly handles ICD messages
  by analyzing logs from the simulation run.

  Scenario: Valid ICD request produces correct response
    Given the simulation logs are loaded
    Then the product logs should contain "Received IcdRequest: test-001"
    And the product logs should contain "Sent IcdResponse: status=OK" within 500ms of the request
    And the simulator logs should confirm "IcdResponse received with status OK"
    And no error entries should appear in the product logs

  Scenario: All ICD responses are within latency threshold
    Given the simulation logs are loaded
    Then every IcdResponse should occur within 500ms of its corresponding IcdRequest
    And the average response time should be less than 200ms

  Scenario: No unexpected errors during communication
    Given the simulation logs are loaded
    Then no ERROR or PANIC entries should appear in the product logs
    And the product should not have restarted during the simulation

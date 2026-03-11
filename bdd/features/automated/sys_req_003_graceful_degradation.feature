@REQ:SYS-REQ-003 @VM:SYS-REQ-003-VM-01 @VER:Demonstration
Feature: Graceful Degradation
  Verify that the system continues operating in a degraded mode
  when a non-critical subsystem fails, by analyzing simulation logs.

  Scenario: System continues processing when non-critical subsystem fails
    Given the simulation logs are loaded
    Then the product logs should contain "Non-critical subsystem unavailable"
    And the product logs should contain "Continuing in degraded mode"
    And the product logs should contain "Processed critical message in degraded mode"
    And no crash or panic entries should appear in the product logs
    And the product should not have restarted during the simulation

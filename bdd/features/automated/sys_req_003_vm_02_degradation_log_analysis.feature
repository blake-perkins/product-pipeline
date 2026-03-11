@REQ:SYS-REQ-003 @VM:SYS-REQ-003-VM-02 @VER:Test
Feature: Graceful Degradation Log Analysis
  Verify via log analysis that critical messages continue to be
  processed when the logging subsystem is disabled.

  Scenario: Critical messages processed during subsystem failure
    Given the simulation logs are loaded
    Then the product logs should contain "Non-critical subsystem unavailable"
    And the product logs should contain "Processed critical message in degraded mode"
    And no ERROR or PANIC entries should appear in the product logs

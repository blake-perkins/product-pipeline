@REQ:SYS-REQ-005
Feature: Error Message Handling
  Verify the system rejects malformed ICD messages gracefully.

  @VM:SYS-REQ-005-VM-01 @VER:Test
  Scenario: Malformed messages are rejected with warnings
    Given the simulation logs are loaded
    Then the product logs should contain "Malformed message rejected"
    And no crash or panic entries should appear in the product logs
    And the product should not have restarted during the simulation

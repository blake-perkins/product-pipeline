@REQ:SYS-REQ-002
Feature: Health Monitoring
  Verify that the system reports health status at configured intervals.

  @VM:SYS-REQ-002-VM-01 @VER:Test
  Scenario: Health status messages are emitted
    Given the simulation logs are loaded
    Then the product logs should contain "HealthStatus"
    And no error entries should appear in the product logs

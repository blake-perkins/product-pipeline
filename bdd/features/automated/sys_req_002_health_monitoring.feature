@REQ:SYS-REQ-002 @VER:Test
Feature: Health Monitoring
  Verify that the system reports health status at configured intervals.

  Scenario: Health status messages are emitted
    Given the simulation logs are loaded
    Then the product logs should contain "HealthStatus"
    And no error entries should appear in the product logs

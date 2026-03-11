@REQ:SYS-REQ-001 @VM:SYS-REQ-001-VM-02 @VER:Demonstration
Feature: ICD Round-Trip Demonstration
  Demonstrate correct round-trip ICD message exchange with the
  simulator under nominal conditions by analyzing simulation logs.

  Scenario: Demonstrate successful ICD round-trip with simulator
    Given the simulation logs are loaded
    Then the product logs should contain "Received IcdRequest: test-001"
    And the product logs should contain "Sent IcdResponse: status=OK"
    And the simulator logs should confirm "IcdResponse received with status OK"
    And the product should not have restarted during the simulation

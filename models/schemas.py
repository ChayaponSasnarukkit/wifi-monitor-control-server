from pydantic import BaseModel
from fastapi import HTTPException
from typing import List, Optional
from models.models import Scenario, Simulation, NodeConfiguration

class CreateScenarioRequest(BaseModel):
    scenario_name: str
    scenario_desc: str
    is_using_target_ap: bool
    target_ap_ssid: Optional[str]
    target_ap_password: Optional[str]
    
    def validate_target_ap(self):
        if self.is_using_target_ap:
            if not self.target_ap_ssid:
                raise HTTPException(400, "target_ap_ssid is required when scenario is using target_ap")
            if not self.target_ap_password:
                raise HTTPException(400, "target_ap_password is required when scenario is using target_ap")

    def _to_new_model(self) -> Scenario:
        if self.is_using_target_ap:
            new_scenario = Scenario(
                scenario_name=self.scenario_name,
                scenario_desc = self.scenario_desc,
                is_using_target_ap = self.is_using_target_ap,
                target_ap_ssid = self.target_ap_ssid,
                target_ap_password = self.target_ap_password
            )
        else:
            new_scenario = Scenario(
                scenario_name=self.scenario_name,
                scenario_desc = self.scenario_desc,
                is_using_target_ap = self.is_using_target_ap,
            )
        return new_scenario
    
    def _to_exist_model(self, scenario: Scenario) -> Scenario:
        if self.is_using_target_ap:
            scenario.scenario_name=self.scenario_name,
            scenario.scenario_desc = self.scenario_desc,
            scenario.is_using_target_ap = self.is_using_target_ap,
            scenario.target_ap_ssid = self.target_ap_ssid,
            scenario.target_ap_password = self.target_ap_password
        else:
            scenario.scenario_name=self.scenario_name,
            scenario.scenario_desc = self.scenario_desc,
            scenario.is_using_target_ap = self.is_using_target_ap,
        return scenario


            
    
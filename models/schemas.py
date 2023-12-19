from pydantic import BaseModel
from fastapi import HTTPException
from typing import List, Optional
from models.models import Scenario, Simulation, NodeConfiguration

class ScenarioRequest(BaseModel):
    scenario_name: str
    scenario_desc: str
    is_using_target_ap: bool = False
    target_ap_ssid: Optional[str] = None
    target_ap_password: Optional[str] = None
    
    def validate_target_ap(self):
        if self.is_using_target_ap:
            if not self.target_ap_ssid:
                raise HTTPException(400, "target_ap_ssid is required when scenario is using target_ap")
            if not self.target_ap_password:
                raise HTTPException(400, "target_ap_password is required when scenario is using target_ap")
        else:
            self.target_ap_ssid = None
            self.target_ap_password = None
            
    
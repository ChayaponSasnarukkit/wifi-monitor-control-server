from pydantic import BaseModel
from fastapi import HTTPException
from typing import List, Optional
from models.models import Scenario, Simulation, NodeConfiguration, NetworkModeEnum

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
            
class ScenarioListResponse(BaseModel):
    scenario_id: int
    scenario_name: str
    is_using_target_ap: bool
    class Config():
        from_attributes = True    
            
DEFAULT_DETER = {
    "simulation_type": "deterministic",
    "timeout": 300,
    "average_interval_time": 10, #ms
    "average_packet_size": 128,
}
    
DEFAULT_WEB = {
    "simulation_type": "web_application",
    "timeout": 300,
    "average_interval_time": 10000, #lambda 10 sec
    "average_packet_size": 1024,
    "average_new_page_packet_size": 2048,
    "probability_of_load_new_page": 30,
}

DEFAULT_FILE = {
    "simulation_type": "file_transfer",
    "timeout": 300,
    "average_packet_size": 1048576, #this will mean file size = 10 MB
}

MAP_DEFAULT = {
    "deterministic": DEFAULT_DETER,
    "web_application": DEFAULT_WEB,
    "file_transfer": DEFAULT_FILE,
}
class NodeConfigRequest(BaseModel):
    control_ip_addr: str
    alias_name: Optional[str] = None
    network_mode: NetworkModeEnum # ap, client
    network_ssid: str
    simulation_detail: Optional[dict] = None # will be ignore if mode==AP
    # (required when using client mode)
    
    def _model_dump(self):
        if self.alias_name is None:
            self.alias_name = self.control_ip_addr
        if self.network_mode == NetworkModeEnum.ap:
            return self.model_dump(exclude_unset=True)
        elif self.network_mode == NetworkModeEnum.client:
            if "simulation_type" not in self.simulation_detail:
                raise HTTPException(400, "simulation_type require when using client mode")
            if self.simulation_detail["simulation_type"] not in MAP_DEFAULT:
                raise HTTPException(400, "simulation_type not support")
            default_detail =  MAP_DEFAULT[self.simulation_detail["simulation_type"]]
            for key in self.simulation_detail:
                if key not in default_detail:
                    raise HTTPException(400, f"options {key} is not valid for simulation type {self.simulation_detail['simulation_type']}")
            for key in default_detail:
                if key not in self.simulation_detail:
                    self.simulation_detail[key] = default_detail[key] # use default
            return self.model_dump(exclude_unset=True)
        else:
            raise HTTPException(400, "network_mode must be client or ap only.")
        
class NodeConfigList(BaseModel):
    id: int
    control_ip_addr: str
    alias_name: str
    network_mode: NetworkModeEnum # ap, client
    network_ssid: str
    class Config():
        from_attributes = True 
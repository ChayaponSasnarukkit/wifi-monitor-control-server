from models.models import Scenario, Simulation, NodeConfiguration, NetworkModeEnum
from models.schemas import NodeConfigRequest
from typing import List
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
    

def parse_network_from_node_config(node_configs: List[NodeConfiguration], target_ap_ssid: str) -> dict:
    enable_to_run = True
    network_info = {}
    warning_message = {}
    # find every ap in network and check if there are having ap
    for node in node_configs:
        if node.network_ssid not in network_info:
            network_info[node.network_ssid] = {
                "is_target_ap": node.network_ssid == target_ap_ssid,
                "aps": {},
                "clients": {}
            }
        if node.network_mode == NetworkModeEnum.ap:
            network_info[node.network_ssid]["aps"][node.control_ip_addr] = {
                "alias_name": node.alias_name,
                "tx_power": node.tx_power if node.tx_power is not None else 20,
                "radio": node.radio if node.radio is not None else "5G",
                "timeout": 0 if len(network_info[node.network_ssid]["clients"]) == 0 else max([network_info[node.network_ssid]["clients"][client]["timeout"] for client in network_info[node.network_ssid]["clients"]]),
                "sever_types": [],
            }
        else:
            network_info[node.network_ssid]["clients"][node.control_ip_addr] = dict(node.simulation_detail).copy()
            network_info[node.network_ssid]["clients"][node.control_ip_addr]["alias_name"] = node.alias_name
            # update ap ones
            for ap_ip in network_info[node.network_ssid]["aps"]:
                network_info[node.network_ssid]["aps"][ap_ip]["timeout"] = max(
                    network_info[node.network_ssid]["aps"][ap_ip]["timeout"],
                    network_info[node.network_ssid]["clients"][node.control_ip_addr]["timeout"]
                )
                if network_info[node.network_ssid]["clients"][node.control_ip_addr]["simulation_type"] not in network_info[node.network_ssid]["aps"][ap_ip]["sever_types"]:
                    network_info[node.network_ssid]["aps"][ap_ip]["sever_types"].append(network_info[node.network_ssid]["clients"][node.control_ip_addr]["simulation_type"])
    # find warning:
    #   1. have multiple aps in same ssid
    #   2. not having ap and that ssid is not the target_ap
    for ssid in network_info:
        if not network_info[ssid]["is_target_ap"] and len(network_info[ssid]["aps"]) == 0:
            enable_to_run = False
            if ssid not in warning_message:
                warning_message[ssid] = []
            warning_message[ssid].append(f"there aren't any ap exist in this network")
        if len(network_info[ssid]["aps"]) > 1:
            enable_to_run = False
            if ssid not in warning_message:
                warning_message[ssid] = []
            warning_message[ssid].append(f"there are multiple aps exist in this network, include {network_info[ssid]['aps'].keys()}")
    
    return {
        "enable_to_run": enable_to_run,
        "warning_message": warning_message,
        "network_info": network_info 
    }

    {
        "ap_2.4G_a": {
            "is_target_ap": False,
            "aps": {
                "192.168.0.2": {
                    "alias_name": "...",
                    "timeout": "...",
                    "sever_types": ["real", "web", "file"],
                }
            },
            "clients": {
                "192.168.0.1": {
                    "alias_name": "...",
                    "timeout": "...",
                    "...": "...",
                }
            }
        },
        
    }
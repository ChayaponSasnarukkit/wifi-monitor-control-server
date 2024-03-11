from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from models.models import Scenario, Simulation, NodeConfiguration
from models.schemas import NodeConfigRequest, NodeConfigList, KeepAliveRequest
from service import node_config_services
from utils.dependency import DBSessionDep

router = APIRouter(
    prefix="/scenario/{scenario_id}/node",
    tags=["node_configurations"],
)

@router.post("/keep_alive", status_code=200)
async def keep_alive(scenario_id: int, request_body: KeepAliveRequest):
    return (await node_config_services.recv_keep_alive_msg(scenario_id, request_body))

@router.get("/keep_alive", status_code=200)
async def keep_alive():
    return (await node_config_services.get_keep_alive_msg())

@router.post("", status_code=200)
async def create_new_scenario(db_session: DBSessionDep, scenario_id: int, request_body: NodeConfigRequest):
    return (await node_config_services.create_node_config(db_session, scenario_id, request_body))

@router.get("", status_code=200)
async def list_node_configs(db_session: DBSessionDep, scenario_id: int, page_size: Optional[int] = 10, page: Optional[int] = 1, search: Optional[str] = ""):
    return (await node_config_services.list_node_configs(db_session, scenario_id, page_size, page, search))

@router.get("/preview", status_code=200)
async def list_node_configs(db_session: DBSessionDep, scenario_id: int):
    return (await node_config_services.preview_node_configs(db_session, scenario_id))

@router.get("/{node_config_id}", status_code=200)
async def get_node_config(db_session: DBSessionDep, scenario_id: int, node_config_id: int):
    return (await node_config_services.get_node_config(db_session, node_config_id))

@router.patch("/{node_config_id}", status_code=200)
async def update_node_config(db_session: DBSessionDep, scenario_id: int, node_config_id: int, request_body: NodeConfigRequest):
    return (await node_config_services.update_node_config(db_session, node_config_id, request_body))

@router.delete("/{node_config_id}", status_code=200)
async def delete_node_config(db_session: DBSessionDep, scenario_id: int, node_config_id: int):
    return (await node_config_services.delete_node_config(db_session, node_config_id))
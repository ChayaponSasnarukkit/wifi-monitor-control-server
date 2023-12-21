from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from models.models import Scenario, Simulation, NodeConfiguration
from models.schemas import NodeConfigRequest
from service import node_config_services
from utils.dependency import DBSessionDep

router = APIRouter(
    prefix="/scenario/{scenario_id}/node",
    tags=["node_configurations"],
)

@router.post("", status_code=200)
async def create_new_scenario(db_session: DBSessionDep, scenario_id: int, request_body: NodeConfigRequest):
    return (await node_config_services.create_node_config(db_session, scenario_id, request_body))

@router.patch("/{node_config_id}", status_code=200)
async def update_scenario(db_session: DBSessionDep, scenario_id: int, node_config_id: int, request_body: NodeConfigRequest):
    return (await node_config_services.update_node_config(db_session, node_config_id, request_body))
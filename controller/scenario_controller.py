from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from models.models import Scenario, Simulation, NodeConfiguration
from models.schemas import ScenarioRequest, ScenarioListResponse
from service import scenario_services
from utils.dependency import DBSessionDep

router = APIRouter(
    prefix="/scenario",
    tags=["scenarios"],
)

@router.post("", status_code=200)
async def create_new_scenario(db_session: DBSessionDep, request_body: ScenarioRequest):
    return (await scenario_services.create_scenario(db_session, request_body))

@router.get("", response_model=List[ScenarioListResponse], status_code=200)
async def list_scenarios(db_session: DBSessionDep, page_size: Optional[int] = 10, page: Optional[int] = 1, search: Optional[str] = ""):
    return (await scenario_services.list_scenarios(db_session, page_size, page, search))

@router.get("/{scenario_id}", status_code=200)
async def get_scenario(db_session: DBSessionDep, scenario_id: int):
    return (await scenario_services.get_scenario(db_session, scenario_id))

@router.patch("/{scenario_id}", status_code=200)
async def update_scenario(db_session: DBSessionDep, scenario_id: int, request_body: ScenarioRequest):
    return (await scenario_services.update_scenario(db_session, request_body, scenario_id))

@router.delete("/{scenario_id}", status_code=200)
async def delete_scenario(db_session: DBSessionDep, scenario_id: int):
    return (await scenario_services.delete_scenario(db_session, scenario_id))

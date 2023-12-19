from fastapi import APIRouter, Depends, HTTPException
from models.models import Scenario, Simulation, NodeConfiguration
from models.schemas import ScenarioRequest
from service import scenario_services
from utils.dependency import DBSessionDep

router = APIRouter(
    prefix="/scenario",
    tags=["scenarios"],
)

@router.post("", status_code=200)
async def create_new_scenario(db_session: DBSessionDep, request_body: ScenarioRequest):
    return (await scenario_services.create_scenario(db_session, request_body))

@router.patch("/{scenario_id}", status_code=200)
async def update_scenario(db_session: DBSessionDep, scenario_id: int, request_body: ScenarioRequest):
    return (await scenario_services.update_scenario(db_session, request_body, scenario_id))
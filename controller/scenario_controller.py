from fastapi import APIRouter, Depends, HTTPException
from models.models import Scenario, Simulation, NodeConfiguration
from models.schemas import CreateScenarioRequest
from service import scenario_services
from utils.dependency import DBSessionDep

router = APIRouter(
    prefix="/scenario",
    tags=["scenarios"],
)

@router.post("", status_code=200)
async def create_new_scenario(db_session: DBSessionDep, request_body: CreateScenarioRequest):
    return (await scenario_services.create_scenario(db_session, request_body))
from fastapi import APIRouter, Request, Depends, HTTPException
from typing import Optional, List
from models.models import Scenario, Simulation, NodeConfiguration
from models.schemas import SimulationList, RunSimulationTitle
from service import simulation_services
from utils.dependency import DBSessionDep

router = APIRouter(
    prefix="/scenario/{scenario_id}/simulation",
    tags=["simulations"],
)

@router.post("/run", status_code=200)
async def run_simulation(db_session: DBSessionDep, scenario_id: int, request_body: RunSimulationTitle, request: Request):
    return (await simulation_services.run_simulation(request.app.lock, db_session, request_body, request, scenario_id))

@router.post("/{simulation_id}/cancel", status_code=200)
async def cancel_simulation(db_session: DBSessionDep, scenario_id: int, simulation_id: int, request: Request):
    return (await simulation_services.cancel_simulation(request.app.lock, db_session, request, scenario_id, simulation_id))

@router.get("", response_model=List[SimulationList], status_code=200)
async def list_simulation(db_session: DBSessionDep, scenario_id: int, page_size: Optional[int] = 10, page: Optional[int] = 1, search: Optional[str] = ""):
    return (await simulation_services.list_simulations(db_session, scenario_id, page_size, page, search))

@router.get("/{simulation_id}", status_code=200)
async def get_simulation(db_session: DBSessionDep, scenario_id: int, simulation_id: int):
    return (await simulation_services.get_simulation(db_session, simulation_id))

@router.delete("/{simulation_id}", status_code=200)
async def delete_node_config(db_session: DBSessionDep, scenario_id: int, simulation_id: int):
    return (await simulation_services.delete_simulation(db_session, simulation_id))
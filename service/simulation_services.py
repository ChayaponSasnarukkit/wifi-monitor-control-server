import asyncio
from datetime import datetime
from models.models import Scenario, Simulation, NodeConfiguration
from models.schemas import RunSimulationTitle
from utils.utils import parse_network_from_node_config
from utils.tasks import simulation_tasks
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_


async def run_simulation(lock: asyncio.Lock, db_session: AsyncSession, request_body: RunSimulationTitle, request: Request, scenario_id: int):
    scenario = (
        await db_session.scalars(
            select(Scenario)
            .where(Scenario.scenario_id==scenario_id)
            .limit(1)
        )
    ).first()
    if not scenario:
        raise HTTPException(404, "scenario not found")
    node_configs = (
        await db_session.scalars(
            select(NodeConfiguration)
            .where(
                NodeConfiguration.scenario==scenario
            )
        )
    ).all()
    
    network_preview = parse_network_from_node_config(node_configs, scenario.target_ap_ssid) if scenario.is_using_target_ap else parse_network_from_node_config(node_configs, "")
    if not network_preview["enable_to_run"]:
        raise HTTPException(400, network_preview)
    
    terminated_state = ["cancelled [terminate with success]", "cancelled [terminate with error]", "failed", "finished"]
    async with lock:
        lastest_simulation = (
            await db_session.scalars(
                select(Simulation)
                .order_by(Simulation.created_at.desc())
            )
        ).first()
        if lastest_simulation and lastest_simulation.state not in terminated_state:
            raise HTTPException(400, "there are simulation running now")
        # create new simulation record
        new_simulation = Simulation(
            title=request_body.title,
            scenario_snapshot=network_preview["network_info"],
            state="starting",
            created_at=datetime.now(),
            scenario=scenario
        )
        db_session.add(new_simulation)
        await db_session.commit()
        await db_session.refresh(new_simulation)
        # schedule the task
        request.app.running_task = asyncio.create_task(
            simulation_tasks(
                lock, 
                db_session, 
                request, 
                new_simulation, 
                network_preview["network_info"], 
                scenario.target_ap_password, 
                scenario.target_ap_radio
            )
        )
        return {"detail": "task has been scheduled", "simulation": new_simulation}

async def cancel_simulation(lock: asyncio.Lock, db_session: AsyncSession, request: Request, scenario_id: int, simulation_id: int):
    can_cancel_states = ["starting", "configuring access point", "configuring client wifi", "running simulation"]
    async with lock:
        simulation = (
            await db_session.scalars(
                select(Simulation)
                .where(Simulation.id==simulation_id)
                .limit(1)
            )
        ).first()
        if simulation.state in can_cancel_states and request.app.running_task is not None:
            request.app.running_task.cancel()
            return {"detail": "Cancel Signal has been sent"}
        return {"detail": "Cancel Signal has been sent"}

async def list_simulations(db_session: AsyncSession, scenario_id: int, page_size: int, page: int, search: str):
    scenario = (
        await db_session.scalars(
            select(Scenario)
            .where(Scenario.scenario_id==scenario_id)
            .limit(1)
        )
    ).first()
    if not scenario:
        raise HTTPException(404, "scenario not found")
    simulations = (
        await db_session.scalars(
            select(
                Simulation
            )
            .where(
                and_(
                    Simulation.title.regexp_match(search),
                    Simulation.scenario==scenario
                )
            )
            .order_by(Simulation.created_at.desc())
            .limit(page_size)
            .offset((page-1)*page_size)
        )
    ).all()
    print(simulations)
    return simulations

async def get_simulation(db_session: AsyncSession, simulation_id: int):
    simulation = (
        await db_session.scalars(
            select(Simulation)
            .where(Simulation.id==simulation_id)
            .limit(1)
        )
    ).first()
    if not simulation:
        raise HTTPException(404, "simulation not found")
    return simulation
        
async def delete_simulation(db_session: AsyncSession, simulation_id: int):
    simulation = (
        await db_session.scalars(
            select(Simulation)
            .where(Simulation.id==simulation_id)
            .limit(1)
        )
    ).first()
    if not simulation:
        raise HTTPException(404, "simulation not found")
    await db_session.delete(simulation)
    await db_session.commit()
    return {"message": "done"}
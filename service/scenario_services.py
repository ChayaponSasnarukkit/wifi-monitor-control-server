from models.models import Scenario, Simulation, NodeConfiguration
from models.schemas import ScenarioRequest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

async def create_scenario(db_session: AsyncSession, request_body: ScenarioRequest):
    # validate request
    request_body.validate_target_ap()
    # create new object
    payload = request_body.model_dump(exclude_unset=True)
    new_scenario = Scenario(**payload)
    # write db
    db_session.add(new_scenario)
    await db_session.commit()
    await db_session.refresh(new_scenario)
    # return new response
    return new_scenario

async def list_scenarios(db_session: AsyncSession, page_size: int, page: int, search: str):
    scenarios = (
        await db_session.scalars(
            select(Scenario)
            .where(Scenario.scenario_name.regexp_match(search))
            .limit(page_size)
            .offset((page-1)*page_size)
        )
    ).all()
    
    return scenarios

async def get_scenario(db_session: AsyncSession, scenario_id: int):
    # query scenario
    scenario = (
        await db_session.scalars(
            select(Scenario)
            .where(Scenario.scenario_id==scenario_id)
            .limit(1)
        )
    ).first()
    if not scenario:
        raise HTTPException(404, "scenario not found")
    return scenario

async def update_scenario(db_session: AsyncSession, request_body: ScenarioRequest, scenario_id: int):
    # validate request
    request_body.validate_target_ap()
    # query scenario
    scenario = (
        await db_session.scalars(
            select(Scenario)
            .where(Scenario.scenario_id==scenario_id)
            .limit(1)
        )
    ).first()
    if not scenario:
        raise HTTPException(404, "scenario not found")
    # update scenario
    payload = request_body.model_dump(exclude_unset=True)
    for key, value in payload.items():
            setattr(scenario, key, value)
    # write to db
    await db_session.commit()
    await db_session.refresh(scenario)
    return scenario

async def delete_scenario(db_session: AsyncSession, scenario_id: int):
    # query scenario
    scenario = (
        await db_session.scalars(
            select(Scenario)
            .where(Scenario.scenario_id==scenario_id)
            .limit(1)
        )
    ).first()
    if not scenario:
        raise HTTPException(404, "scenario not found")
    # delete scenario
    await db_session.execute(
        delete(NodeConfiguration)
        .where(NodeConfiguration.scenario==scenario)
    )
    await db_session.execute(
        delete(Simulation)
        .where(Simulation.scenario==scenario)
    )
    await db_session.delete(scenario)
    await db_session.commit()
    return {"message": "done"}
    
    
    
    
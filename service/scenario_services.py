from models.models import Scenario, Simulation, NodeConfiguration
from models.schemas import ScenarioRequest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

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
    
    
    
    
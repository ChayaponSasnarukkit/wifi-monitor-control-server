from models.models import Scenario, Simulation, NodeConfiguration
from models.schemas import CreateScenarioRequest
from sqlalchemy.ext.asyncio import AsyncSession

async def create_scenario(db_session: AsyncSession, request_body: CreateScenarioRequest):
    # validate request
    request_body.validate_target_ap()
    # create new object
    new_scenario = request_body._to_new_model()
    # write db
    db_session.add(new_scenario)
    await db_session.commit()
    await db_session.refresh(new_scenario)
    # return
    return new_scenario
    
    
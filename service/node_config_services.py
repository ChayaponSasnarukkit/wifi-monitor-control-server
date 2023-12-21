from models.models import Scenario, Simulation, NodeConfiguration
from models.schemas import NodeConfigRequest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

async def create_node_config(db_session: AsyncSession, scenario_id: int, request_body: NodeConfigRequest):
    # validate request
    scenario = (
        await db_session.scalars(
            select(Scenario)
            .where(Scenario.scenario_id==scenario_id)
            .limit(1)
        )
    ).first()
    if not scenario:
        raise HTTPException(404, "scenario not found")
    # create new object
    payload = request_body._model_dump()
    payload["scenario"] = scenario
    new_node = NodeConfiguration(**payload)
    # write db
    db_session.add(new_node)
    await db_session.commit()
    await db_session.refresh(new_node)
    # return new response
    return new_node

async def list_node_configs(db_session: AsyncSession, scenario_id: int, page_size: int, page: int, search: str):
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
                and_(
                    NodeConfiguration.alias_name.regexp_match(search),
                    NodeConfiguration.scenario==scenario
                )
            )
            .limit(page_size)
            .offset((page-1)*page_size)
        )
    ).all()
    
    return node_configs

async def update_node_config(db_session: AsyncSession, node_config_id: int, request_body: NodeConfigRequest):
    # validate request
    node_config = (
        await db_session.scalars(
            select(NodeConfiguration)
            .where(NodeConfiguration.id==node_config_id)
            .limit(1)
        )
    ).first()
    if not node_config:
        raise HTTPException(404, "node_config not found")
    # create new object
    payload = request_body._model_dump()
    for key, value in payload.items():
        setattr(node_config, key, value)
    # write db
    await db_session.commit()
    await db_session.refresh(node_config)
    # return new response
    return node_config

async def get_node_config(db_session: AsyncSession, node_config_id: int):
    node_config = (
        await db_session.scalars(
            select(NodeConfiguration)
            .where(NodeConfiguration.id==node_config_id)
            .limit(1)
        )
    ).first()
    if not node_config:
        raise HTTPException(404, "node_config not found")
    return node_config

async def delete_node_config(db_session: AsyncSession, node_config_id: int):
    node_config = (
        await db_session.scalars(
            select(NodeConfiguration)
            .where(NodeConfiguration.id==node_config_id)
            .limit(1)
        )
    ).first()
    if not node_config:
        raise HTTPException(404, "node_config not found")
    await db_session.delete(node_config)
    await db_session.commit()
    return {"message": "done"}
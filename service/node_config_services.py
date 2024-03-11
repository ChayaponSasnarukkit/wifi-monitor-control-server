from models.models import Scenario, Simulation, NodeConfiguration
from models.schemas import NodeConfigRequest, KeepAliveRequest
from utils.utils import parse_network_from_node_config
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
import time

active_last_seen = {}

async def recv_keep_alive_msg(scenario_id: int, request_body: KeepAliveRequest):
    active_last_seen[request_body.control_ip] = time.time()
    return {"message": "done"}
    
async def get_keep_alive_msg():
    tmp = {}
    for ip in active_last_seen:
        if time.time() >= active_last_seen[ip] + 180:
            pass
        else:
            tmp[ip] = active_last_seen[ip]
    return tmp

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
    
    node_configs_list = [{k: v for k, v in node_config.__dict__.items() if k != '_sa_instance_state'} for node_config in node_configs]
    for node_config in node_configs_list:
        if node_config["control_ip_addr"] in active_last_seen and time.time() < active_last_seen[node_config["control_ip_addr"]] + 180:
            node_config["status"] = "active"
        else:
            node_config["status"] = "inactive"
    return node_configs_list

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

    node_config_dict = {k: v for k, v in node_config.__dict__.items() if k != '_sa_instance_state'}
    if node_config_dict["control_ip_addr"] in active_last_seen and time.time() < active_last_seen[node_config_dict["control_ip_addr"]] + 180:
            node_config_dict["status"] = "active"
    else:
        node_config_dict["status"] = "inactive"
    return node_config_dict

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

async def preview_node_configs(db_session: AsyncSession, scenario_id: int):
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
    
    return parse_network_from_node_config(node_configs, scenario.target_ap_ssid) if scenario.is_using_target_ap else parse_network_from_node_config(node_configs, "")
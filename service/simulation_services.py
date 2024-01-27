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
    map_client_to_ap = {}
    for ssid in simulation.scenario_snapshot:
        if len((simulation.scenario_snapshot[ssid]["aps"])) > 0:
            ap_control_ip = next(iter(simulation.scenario_snapshot[ssid]["aps"]))
        else:
            ap_control_ip = "this_device"
        for client in simulation.scenario_snapshot[ssid]["clients"]:
            map_client_to_ap[client] = ap_control_ip
    # print(simulation.simulation_data)
    simulation_data = {}
    simulation_udp_deterministic_client_data = {}
    simulation_udp_deterministic_server_data = {}
    # print(simulation.simulation_data)
    for control_ip in simulation.simulation_data:
        if control_ip != "this_device":
            simulation_data[control_ip] = {field: simulation.simulation_data[control_ip][field] for field in simulation.simulation_data[control_ip] if field in {"Tx-Power", "Signal", "Noise", "BitRate"}}
        if "udp_deterministic_client_data_monitored_from_server" in simulation.simulation_data[control_ip]:
            client_data = simulation.simulation_data[control_ip]["udp_deterministic_client_data_monitored_from_server"]
            simulation_udp_deterministic_client_data[control_ip] = {}
            for client_ip in client_data:
                # [read_timestamp, seq_number, (send_timestamp, diff, len(data))]
                until = 0; expected_seq=0; tmp_latency_data = []; tmp_lost_data = []
                for data in client_data[client_ip]:
                    # move to next one sec
                    if data[0] >= until:
                        if until > 0:
                            tmp_latency_data.append((data[0], sum_latency/cnt))
                            tmp_lost_data.append((data[0], lost))
                        cnt = 0; lost = 0; sum_latency = 0; until = data[0] + 1
                    sum_latency += data[2][1]
                    # ไม่ลองรับ out-of-order
                    lost += data[1] - expected_seq
                    expected_seq = data[1] + 1
                    cnt += 1
                simulation_udp_deterministic_client_data[control_ip][client_ip] = {"lost_count": tmp_lost_data, "average_latency": tmp_latency_data}
        if "udp_deterministic_server_data_monitored_from_client" in simulation.simulation_data[control_ip]:
            server_data = simulation.simulation_data[control_ip]["udp_deterministic_server_data_monitored_from_client"]
            ap_control_ip = map_client_to_ap[control_ip]
            if ap_control_ip not in simulation_udp_deterministic_server_data:
                simulation_udp_deterministic_server_data[ap_control_ip] = {}
            until = 0; expected_seq=0; tmp_latency_data = []; tmp_lost_data = []
            print(len(server_data))
            for data in server_data:
                # move to next one sec
                if data[0] >= until:
                    if until > 0:
                        tmp_latency_data.append((data[0], sum_latency/cnt))
                        tmp_lost_data.append((data[0], lost))
                    cnt = 0; lost = 0; sum_latency = 0; until = data[0] + 1
                sum_latency += data[2][1]
                # ไม่ลองรับ out-of-order
                lost += data[1] - expected_seq
                expected_seq = data[1] + 1
                cnt += 1
            if control_ip not in simulation_udp_deterministic_server_data[ap_control_ip]:
                simulation_udp_deterministic_server_data[ap_control_ip][control_ip] = {}
            simulation_udp_deterministic_server_data[ap_control_ip][control_ip].update({"lost_count": tmp_lost_data, "average_latency": tmp_latency_data})
        if "file_average_data_rates" in simulation.simulation_data[control_ip]:
            server_data = simulation.simulation_data[control_ip]["file_average_data_rates"]
            ap_control_ip = map_client_to_ap[control_ip]
            if ap_control_ip not in simulation_udp_deterministic_server_data:
                simulation_udp_deterministic_server_data[ap_control_ip] = {}
            tmp_data_rates = []
            if len(server_data) > 0:
                start_time = server_data[0][0]
                data_rate_sum = server_data[0][1]/(server_data[0][0] - server_data[0][2])
                cnt = 1
                tmp_data_rates.append((server_data[0][0], data_rate_sum/cnt))
                now = start_time + 1
            print(len(server_data))
            for data in server_data:
                if data[0] >= now:
                    tmp_data_rates.append((now, data_rate_sum/cnt))
                    now += 1
                    while data[0] - now >= 1:
                        tmp_data_rates.append((now, data_rate_sum/cnt))
                        now += 1
                data_rate_sum += data[1]/(data[0] - data[2])
                cnt += 1
                if data == server_data[-1]:
                    tmp_data_rates.append((now, data_rate_sum/cnt))            
            if control_ip not in simulation_udp_deterministic_server_data[ap_control_ip]:
                simulation_udp_deterministic_server_data[ap_control_ip][control_ip] = {}
            simulation_udp_deterministic_server_data[ap_control_ip][control_ip].update({"file_average_data_rates": tmp_data_rates})
        if "web_average_data_rates" in simulation.simulation_data[control_ip]:
            server_data = simulation.simulation_data[control_ip]["web_average_data_rates"]
            ap_control_ip = map_client_to_ap[control_ip]
            if ap_control_ip not in simulation_udp_deterministic_server_data:
                simulation_udp_deterministic_server_data[ap_control_ip] = {}
            tmp_data_rates = []
            if len(server_data) > 0:
                start_time = server_data[0][0]
                data_rate_sum = server_data[0][1]/(server_data[0][0] - server_data[0][2])
                cnt = 1
                tmp_data_rates.append((server_data[0][0], data_rate_sum/cnt))
                now = start_time + 1
            print(len(server_data))
            for data in server_data:
                if data[0] >= now:
                    tmp_data_rates.append((now, data_rate_sum/cnt))
                    now += 1
                    while data[0] - now >= 1:
                        tmp_data_rates.append((now, data_rate_sum/cnt))
                        now += 1
                data_rate_sum += data[1]/(data[0] - data[2])
                cnt += 1
                if data == server_data[-1]:
                    tmp_data_rates.append((now, data_rate_sum/cnt)) 
            if control_ip not in simulation_udp_deterministic_server_data[ap_control_ip]:
                simulation_udp_deterministic_server_data[ap_control_ip][control_ip] = {}
            simulation_udp_deterministic_server_data[ap_control_ip][control_ip].update({"web_average_data_rates": tmp_data_rates})
    # simulation_data.update({
    #     "udp_deterministic_server_data_monitored_from_client": simulation_udp_deterministic_server_data,
    #     "udp_deterministic_client_data_monitored_from_server": simulation_udp_deterministic_client_data
    # })
    print(simulation.simulation_data)
    return {
        "id": simulation.id,
        "title": simulation.title,
        "scenario_snapshot": simulation.scenario_snapshot,
        "state": simulation.state,
        "state_message": simulation.state_message,
        "simulation_data": simulation_data,
        "udp_deterministic_server_data_monitored_from_client": simulation_udp_deterministic_server_data,
        "udp_deterministic_client_data_monitored_from_server": simulation_udp_deterministic_client_data,
        "created_at": simulation.created_at,
        "scenario_id": simulation.scenario_id
    }
        
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
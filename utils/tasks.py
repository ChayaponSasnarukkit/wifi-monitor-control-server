import psutil
import asyncio
import aiohttp, os, signal, subprocess
import time
from utils.utils import (
    post_request,
    generate_scripts_for_run_simulation, 
    _get_ip_address, 
    _configure_server_connection, 
    keep_sending_post_request_until_all_ok, 
    send_multiple_get_request,
    RUN_SUBPROCESS_EXCEPTION
)
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from models.models import Scenario, Simulation, RadioModeEnum
from models.database import get_db_session
    
async def simulation_tasks(lock: asyncio.Lock, db_session: AsyncSession, request: Request, simulation: Simulation, parsed_node_configs: dict, target_ssid_password: str, target_ssid_radio: RadioModeEnum):
    try:
        target_ssid_radio = target_ssid_radio.value
        map_ip_to_alias_name = {}
        for ssid in parsed_node_configs:
            for control_ip in parsed_node_configs[ssid]["aps"]:
                map_ip_to_alias_name[control_ip] = parsed_node_configs[ssid]["aps"][control_ip]["alias_name"]
            for control_ip in parsed_node_configs[ssid]["clients"]:
                map_ip_to_alias_name[control_ip] = parsed_node_configs[ssid]["clients"][control_ip]["alias_name"]
        have_monitor_data = False
        # configuring all ap_node
        async with lock:
            simulation.state = "configuring access point"
            db_session.add(simulation)
            await db_session.commit()
        config_ap_request_data = {}
        for ssid in parsed_node_configs:
            if parsed_node_configs[ssid]["is_target_ap"]:
                continue
            for control_ip in parsed_node_configs[ssid]["aps"]:
                config_ap_request_data[control_ip] = {
                    "ssid": ssid,
                    "radio": parsed_node_configs[ssid]["aps"][control_ip]["radio"],
                    "tx_power": parsed_node_configs[ssid]["aps"][control_ip]["tx_power"]
                }
        # sending request until all send the ok respond
        config_data_map_url_data = {f"http://{control_ip}:8000/configure/ap": config_ap_request_data[control_ip] for control_ip in config_ap_request_data}
        await keep_sending_post_request_until_all_ok(db_session, simulation, config_data_map_url_data, map_ip_to_alias_name)
        # start to poll the result
        polling_urls = {f"http://{control_ip}:8000/configure/ap/state": config_ap_request_data[control_ip] for control_ip in config_ap_request_data}    
        finish_urls = set()
        # await 10 second make sure that tx_packets count is being cleared (ตัวเก่าจะช้า 30 วินาที)
        if len(polling_urls) > 0:
            await asyncio.sleep(10)
        # print("somethiong\n\n\n")
        while True:
            # print(polling_urls)
            if len(polling_urls) == len(finish_urls):
                break
            polling_results = await send_multiple_get_request(polling_urls, finish_urls)
            for result in polling_results:
                # print(result)
                if issubclass(type(result), Exception):
                    if result is asyncio.CancelledError:
                        raise result
                    print(result)
                    if type(result.args[0]) is aiohttp.client_reqrep.ConnectionKey:
                        simulation.state_message += f"{map_ip_to_alias_name[result.args[0].host]} {time.time()}: {str(result)}\n"
                    else:
                        simulation.state_message += str(result)+"\n"
                else:
                    if result[0] == "ready_to_use":
                        finish_urls.add(result[1])
                        simulation.state_message += f"{map_ip_to_alias_name[result[1].split(':')[1][2:]]} {time.time()}: {result[0]}\n"
                        print(f"{result[1].split(':')[1][2:]} {time.time()}: {result[0]}\n")
            db_session.add(simulation)
            await db_session.commit()
            await asyncio.sleep(5)
        # ============================================================================================= #
        # configure all client_node
        async with lock:
            simulation.state = "configuring client wifi"
            db_session.add(simulation)
            await db_session.commit()
        have_temp_profile = False
        target_ssid = ""
        config_client_request_data = {}
        for ssid in parsed_node_configs:
            if parsed_node_configs[ssid]["is_target_ap"]:
                target_ssid = ssid
                have_temp_profile = True
                for control_ip in parsed_node_configs[ssid]["clients"]:
                    config_client_request_data[control_ip] = {
                        "ssid": ssid,
                        "password": target_ssid_password,
                        "radio": target_ssid_radio,
                        "connect_to_target_ap": True,
                    }
            else:
                for control_ip in parsed_node_configs[ssid]["clients"]:
                    config_client_request_data[control_ip] = {
                        "ssid": ssid,
                        "radio": next(iter(parsed_node_configs[ssid]["aps"]))["radio"],
                        "connect_to_target_ap": True,
                    }
        # keep sending request until all connected (this url wll wait for configured to apply because connected wifi is way more faster than config ap)
        config_map_url_data = {f"http://{control_ip}:8000/configure/client": config_client_request_data[control_ip] for control_ip in config_client_request_data}    
        print(config_map_url_data)
        await keep_sending_post_request_until_all_ok(db_session, simulation, config_map_url_data, map_ip_to_alias_name)
        # polling until this device successfully connected to target ap
        if have_temp_profile:
            this_device_connected = False
            # print(target_ssid)
            while not this_device_connected:
                try :
                    this_device_connected = await _configure_server_connection(ssid, target_ssid_password)
                except RUN_SUBPROCESS_EXCEPTION as e:
                    # print(str(e))
                    simulation.state_message += f"this_device {time.time()}: {str(e)}"
                # print(this_device_connected)
                await asyncio.sleep(2)
                db_session.add(simulation)
                await db_session.commit()
            this_device_connected_ip = _get_ip_address()
            # print(this_device_connected_ip)
            simulation.state_message += f"this_device {time.time()}: connected to {target_ssid} with ip_address {this_device_connected_ip}\n"
            db_session.add(simulation)
            await db_session.commit()
        # ============================================================================================== #
        # running simulation
        async with lock:
            simulation.state = "running simulation"
            db_session.add(simulation)
            await db_session.commit()
        this_device_simulation_modes = set()
        this_device_server_timeout = 0
        running_request_data = {}
        for ssid in parsed_node_configs:
            if parsed_node_configs[ssid]["is_target_ap"]:
                for control_ip in parsed_node_configs[ssid]["clients"]:
                    this_device_simulation_modes.add(parsed_node_configs[ssid]["clients"][control_ip]["simulation_type"])
                    this_device_server_timeout = max(this_device_server_timeout, parsed_node_configs[ssid]["clients"][control_ip]["timeout"])
                    simulation_scenario = parsed_node_configs[ssid]["clients"][control_ip].copy()
                    simulation_scenario.pop("alias_name")
                    # print(parsed_node_configs[ssid]["clients"][control_ip].copy())
                    running_request_data[control_ip] = {
                        "alias_name": parsed_node_configs[ssid]["clients"][control_ip]["alias_name"],
                        "simulation_mode": "client",
                        "server_ip": this_device_connected_ip,
                        "simulation_scenarios": [
                            simulation_scenario
                        ],
                    }
                continue
            for control_ip in parsed_node_configs[ssid]["aps"]:
                running_request_data[control_ip] = {
                    "alias_name": parsed_node_configs[ssid]["aps"][control_ip]["alias_name"],
                    "simulation_mode": "server",
                    "simulation_scenarios": [
                        {"simulation_type": mode, "timeout": parsed_node_configs[ssid]["aps"][control_ip]["timeout"]} for mode in parsed_node_configs[ssid]["aps"][control_ip]["sever_types"]
                    ],
                }
            for control_ip in parsed_node_configs[ssid]["clients"]:
                running_request_data[control_ip] = {
                    "alias_name": parsed_node_configs[ssid]["clients"][control_ip]["alias_name"],
                    "simulation_mode": "client",
                    "simulation_scenarios": [
                        (parsed_node_configs[ssid]["clients"][control_ip]["alias_name"].copy()).pop("alias_name")
                    ],
                }
        # open server at this device
        # print(running_request_data)
        print("\n\n\n\nksdjfdolsdj\n")
        running_processes = []
        if have_temp_profile and this_device_server_timeout > 0 and len(this_device_simulation_modes) > 0:
            run_scripts = generate_scripts_for_run_simulation(this_device_simulation_modes, this_device_server_timeout+5)
            if len(run_scripts) > 0:
                for script in run_scripts:
                    process = await asyncio.create_subprocess_shell(script, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    running_processes.append(process)
        # keep sending request until task scheduled on all client
        running_map_url_data = {f"http://{control_ip}:8000/simulation/run": running_request_data[control_ip] for control_ip in running_request_data}    
        print("\n\n\n\nksdjfdolsdj\n")
        await keep_sending_post_request_until_all_ok(db_session, simulation, running_map_url_data, map_ip_to_alias_name)
        # polling until all completed
        have_monitor_data = True
        polling_urls = {f"http://{control_ip}:8000/simulation/state": None for control_ip in running_request_data}
        finish_urls = set()
        finish_process = []
        while True:
            if len(polling_urls) != len(finish_urls):
                polling_results = await send_multiple_get_request(polling_urls, finish_urls)
                for result in polling_results:
                    # print(result)
                    if issubclass(type(result), Exception):
                        if result is asyncio.CancelledError:
                            raise result
                        if type(result.args[0]) is aiohttp.client_reqrep.ConnectionKey:
                            simulation.state_message += f"{map_ip_to_alias_name[result.args[0].host]} {time.time()}: {str(result)}\n"
                        else:
                            simulation.state_message += str(result)+"\n"
                    else:
                        if result[0]["state"] == "finish":
                            finish_urls.add(result[1])
                            # alias_name or control_ip
                            # print("\n\n\n", result[0])
                        simulation.state_message += result[0]["new_state_message"]
            if len(running_processes) != len(finish_process):
                for process in running_processes:
                    # print(process)
                    try:
                        # print("AB")
                        stdout = await asyncio.wait_for(process.stdout.read(1024), timeout=0.01)
                        if not stdout:
                            finish_process.append(process)
                            # process is finish writing (write eof to buffer)
                            continue
                        print("aaaa", stdout.decode())
                        simulation.state_message += f"this_device {time.time()}: {stdout.decode()}"
                    except asyncio.TimeoutError:
                        # print("A")
                        pass
            db_session.add(simulation)
            await db_session.commit()
            if len(running_processes) == len(finish_process) and len(polling_urls) == len(finish_urls):
                break
            await asyncio.sleep(2)
        
    except asyncio.CancelledError:
        async with lock:
            simulation.state = "cancelling"
            db_session.add(simulation)
            await db_session.commit()
        # retry 3 time
        if have_monitor_data:
            map_url_data = {f"http://{control_ip}:8000/simulation/cancel": {} for control_ip in running_request_data}   
            polling_urls = {f"http://{control_ip}:8000/simulation/state": None for control_ip in running_request_data}
            finish_urls = set()
            polled_urls = set()
            cnt = 0
            while cnt < 3:
                print(cnt)
                tasks = [post_request(url, map_url_data[url]) for url in map_url_data if url not in finish_urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if issubclass(type(result), Exception):
                        if result is asyncio.CancelledError:
                            raise result
                        if type(result.args[0]) is aiohttp.client_reqrep.ConnectionKey:
                            simulation.state_message += f"{map_ip_to_alias_name[result.args[0].host]} {time.time()}: {str(result)}\n"
                        else:
                            simulation.state_message += str(result)+"\n"
                        # commit()
                    else:
                        finish_urls.add(result[1])
                        simulation.state_message += f"{map_ip_to_alias_name[result[1].split(':')[1][2:]]} {time.time()} : {result[0]}\n"
                        # commit
                polling_results = await send_multiple_get_request(polling_urls, polled_urls)
                for result in polling_results:
                    # print(result)
                    if issubclass(type(result), Exception):
                        if result is asyncio.CancelledError:
                            raise result
                        if type(result.args[0]) is aiohttp.client_reqrep.ConnectionKey:
                            simulation.state_message += f"{map_ip_to_alias_name[result.args[0].host]} {time.time()}: {str(result)}\n"
                        else:
                            simulation.state_message += str(result)+"\n"
                    else:
                        if result[0]["state"] == "finish":
                            polled_urls.add(result[1])
                            # alias_name or control_ip
                            # print("\n\n\n", result[0])
                        simulation.state_message += result[0]["new_state_message"]
                db_session.add(simulation)
                await db_session.commit()
                if len(map_url_data) == len(finish_urls):
                    break
                await asyncio.sleep(2)
                cnt += 1
            if have_temp_profile:
                print(time.time())
                for process in running_processes:
                    print(process)
                    print(process.returncode)
                    if process.returncode is None:
                        print("sending signal")
                        # process.terminate()
                        # os.kill(process.pid, signal.SIGTERM)
                        print(process.pid)
                        result = subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], stdout=subprocess.PIPE)
                        simulation.state_message += f"this_device {time.time()}: {result.stdout.decode()}"
                        print("is this task death")
                        print(process.returncode)
                        stdout, stderr = await process.communicate()
                        print(process.returncode)
                        simulation.state_message += f"this_device {time.time()}: {stdout.decode()}"
                db_session.add(simulation)
                await db_session.commit()
                print(time.time())
            
            async with lock:
                if len(map_url_data) == len(finish_urls):
                    simulation.state = "cancelled [terminate with success]"
                else:
                    simulation.state = "cancelled [terminate with error]"
                db_session.add(simulation)
                await db_session.commit()
        else:
            print("hello")
            async with lock:
                simulation.state = "cancelled [terminate with success]"
                db_session.add(simulation)
                await db_session.commit()
        print("cancel")
    except Exception as e:
        print("????????\n")
        async with lock:
            simulation.state = "failed"
            simulation.state_message += f"failed with unexpected exception: {str(e)}"
            db_session.add(simulation)
            await db_session.commit()
        print(str(e))
    finally:
        async with lock:
            if simulation.state == "running simulation":
                simulation.state = "terminating"
                db_session.add(simulation)
                await db_session.commit()
        if have_monitor_data:
            simulation_data = {control_ip: {"Tx_power": None, "Signal": None, "Noise": None, "BitRate": None} for control_ip in running_request_data}
            polling_urls = {f"http://{control_ip}:8000/simulation/monitor": None for control_ip in running_request_data}
            polling_results = await send_multiple_get_request(polling_urls, {})
            for result in polling_results:
                # print(result)
                if issubclass(type(result), Exception):
                    if result is asyncio.CancelledError:
                        raise result
                else:
                    ip = str(result[1]).split(":")[1][2:]
                    simulation_data[ip] = result[0]
            simulation.simulation_data = simulation_data
            db_session.add(simulation)
            await db_session.commit()
        async with lock:
            if simulation.state == "terminating":
                simulation.state = "finished"
                db_session.add(simulation)
                await db_session.commit()
        request.app.running_task = None
        print(simulation.state_message, simulation.state)
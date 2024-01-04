import psutil
import asyncio
import aiohttp
import subprocess, tempfile, os, time



def _generate_script_for_run_ap_simulation(alias_name: str, mode, timeout):
    if mode == "deterministic":
        return f"python -u ./simulation/server/deterministic.py {alias_name} {timeout}"

def generate_scripts_for_run_simulation(scenario_mode, timeout):
    scripts = []
    for mode in scenario_mode:
        scripts.append(
            _generate_script_for_run_ap_simulation("this_device", mode, timeout))
    return scripts

class RUN_SUBPROCESS_EXCEPTION(Exception):
    pass

async def run_subprocess(command: str):
    process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    exit_status = process.returncode
    if exit_status != 0:
        # print(stderr, stdout)
        raise RUN_SUBPROCESS_EXCEPTION(stderr.decode())
    return stdout, stderr

def _get_ip_address():
    # Use subprocess to get the IP configuration for the WiFi interface
    result = subprocess.run(["ipconfig"], capture_output=True, text=True)
    ipconfig_output = result.stdout

    # Find the WiFi interface information in the output
    wifi_info_start = ipconfig_output.find('Wi-Fi')
    wifi_info = ipconfig_output[wifi_info_start:]
    # print(ipconfig_output)
    # Find the IPv4 address in the WiFi interface information
    ip_start = wifi_info.find('IPv4 Address') + 36
    ip_end = wifi_info.find('\n', ip_start)
    ip_address = wifi_info[ip_start:ip_end].strip()

    return ip_address
async def _configure_server_connection(ssid, password):
    # Configure Server Connection
    # Create a temporary XML profile file
    with open("temp.xml", 'w') as file:
        file.write(f"""
        <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
            <name>{ssid}</name>
            <SSIDConfig>
                <SSID>
                    <name>{ssid}</name>
                </SSID>
            </SSIDConfig>
            <connectionType>ESS</connectionType>
            <connectionMode>auto</connectionMode>
            <MSM>
                <security>
                    <authEncryption>
                        <authentication>WPA2PSK</authentication>
                        <encryption>AES</encryption>
                        <useOneX>false</useOneX>
                    </authEncryption>
                    <sharedKey>
                        <keyType>passPhrase</keyType>
                        <protected>false</protected>
                        <keyMaterial>{password}</keyMaterial>
                    </sharedKey>
                </security>
            </MSM>
        </WLANProfile>
        """)

    # Set the XML profile for the new network
    stdout, stderr = await run_subprocess('netsh wlan add profile filename="temp.xml" interface=Wi-Fi')
    # print(stdout, stderr)
    # Connect to the new network
    stdout, stderr = await run_subprocess(f'netsh wlan connect ssid={ssid} name={ssid} interface=Wi-Fi')
    # print(stdout.decode())
    if "Connection request was completed successfully." in stdout.decode():
        return True
    return False

async def post_request(url: str, data: dict):
    # print(data)
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            url=url,
            json=data,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return (await response.json(content_type=None)), str(response.url)
    
async def get_request(url: str, params: dict = {}):
    async with aiohttp.ClientSession() as session:
        response = await session.get(
            url=url,
            params=params
        )
        # print(str(response.url))
        return (await response.json(content_type=None)), str(response.url)
    
async def keep_sending_post_request_until_all_ok(simulation, map_url_data: dict, update_exception_to_state: bool = True,):
    ok_url = set() # set of url that already recieve 200 status response
    while True:
        tasks = [post_request(url, map_url_data[url]) for url in map_url_data if url not in ok_url]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if issubclass(type(result), Exception):
                if update_exception_to_state:
                    simulation.state_message += str(result)+"\n"
                    # commit()
            else:
                ok_url.add(result[1])
                simulation.state_message += f"{result[1].split(':')[1][2:]} : {result[0]}\n"
                # commit
        if len(map_url_data) == len(ok_url):
            break
        await asyncio.sleep(2)

                
async def send_multiple_get_request(urls: dict, except_urls: set):
   tasks = [get_request(url, urls[url]) for url in urls if url not in except_urls]
   results = await asyncio.gather(*tasks, return_exceptions=True)
   return results         
    
async def simulation_tasks(simulation, parsed_node_configs: dict, target_ssid_password: str, target_ssid_radio: str, data_location: str):
    try:
        have_monitor_data = False
        # configuring all ap_node
        simulation.state = "configuring access point"
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
        await keep_sending_post_request_until_all_ok(simulation, config_data_map_url_data)
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
                    simulation.state_message += str(result)+"\n"
                else:
                    if result[0] == "ready_to_use":
                        finish_urls.add(result[1])
                        simulation.state_message += f"{result[1].split(':')[1][2:]} : {result[0]}\n"
            await asyncio.sleep(5)
        # ============================================================================================= #
        # configure all client_node
        simulation.state = "configuring client wifi"
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
        await keep_sending_post_request_until_all_ok(simulation, config_map_url_data)
        # polling until this device successfully connected to target ap
        if have_temp_profile:
            this_device_connected = False
            # print(target_ssid)
            while not this_device_connected:
                try :
                    this_device_connected = await _configure_server_connection(ssid, target_ssid_password)
                except RUN_SUBPROCESS_EXCEPTION as e:
                    # print(str(e))
                    simulation.state_message += str(e)
                # print(this_device_connected)
                await asyncio.sleep(2)
            this_device_connected_ip = _get_ip_address()
            # print(this_device_connected_ip)
            simulation.state_message += f"this_device: connected to {target_ssid} with ip_address {this_device_connected_ip}\n"
        # ============================================================================================== #
        # running simulation
        simulation.state = "running simulation"
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
                        {"simulation_type": mode} for mode in parsed_node_configs[ssid]["aps"][control_ip]["sever_types"]
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
        running_processes = []
        if have_temp_profile and this_device_server_timeout > 0 and len(this_device_simulation_modes) > 0:
            run_scripts = generate_scripts_for_run_simulation(this_device_simulation_modes, this_device_server_timeout+5)
            for script in run_scripts:
                process = await asyncio.create_subprocess_shell(script, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                running_processes.append(process)
        # keep sending request until task scheduled on all client
        running_map_url_data = {f"http://{control_ip}:8000/simulation/run": running_request_data[control_ip] for control_ip in running_request_data}    
        await keep_sending_post_request_until_all_ok(simulation, running_map_url_data)
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
                        simulation.state_message += stdout.decode()
                    except asyncio.TimeoutError:
                        # print("A")
                        pass
            if len(running_processes) == len(finish_process) and len(polling_urls) == len(finish_urls):
                break
            await asyncio.sleep(2)
        
    except asyncio.CancelledError:
        simulation.state = "cancelling"
        # retry 3 time
        if have_monitor_data:
            map_url_data = {f"http://{control_ip}:8000/simulation/cancel": {} for control_ip in running_request_data}   
            polling_urls = {f"http://{control_ip}:8000/simulation/state": None for control_ip in running_request_data}
            finish_urls = set()
            polled_urls = set()
            cnt = 0
            while cnt < 3:
                tasks = [post_request(url, map_url_data[url]) for url in map_url_data if url not in finish_urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if issubclass(type(result), Exception):
                        simulation.state_message += str(result)+"\n"
                        # commit()
                    else:
                        finish_urls.add(result[1])
                        simulation.state_message += f"{result[1].split(':')[1][2:]} : {result[0]}\n"
                        # commit
                polling_results = await send_multiple_get_request(polling_urls, polled_urls)
                for result in polling_results:
                    # print(result)
                    if issubclass(type(result), Exception):
                        simulation.state_message += str(result)+"\n"
                    else:
                        if result[0]["state"] == "finish":
                            polled_urls.add(result[1])
                            # alias_name or control_ip
                            # print("\n\n\n", result[0])
                        simulation.state_message += result[0]["new_state_message"]
                if len(map_url_data) == len(finish_urls):
                    break
                await asyncio.sleep(2)
            if have_temp_profile:
                print(time.time())
                for process in running_processes:
                    print(process)
                    print(process.returncode)
                    if process.returncode is None:
                        print("sending signal")
                        process.terminate()
                        stdout, stderr = await process.communicate()
                        simulation.state_message += stdout.decode()
                print(time.time())
            if len(map_url_data) == len(finish_urls):
                simulation.state = "cancelled [terminate with success]"
            else:
                simulation.state = "cancelled [terminate with error]"
        print("cancel")
    except Exception as e:
        print("????????\n")
        simulation.state = "failed"
        simulation.state_message += f"failed with unexpected exception: {str(e)}"
        print(str(e))
    finally:
        print("finally")
        await(1000)
        if have_monitor_data:
            simulation_data = {control_ip: {"Tx_power": None, "Signal": None, "Noise": None, "BitRate": None} for control_ip in running_request_data}
            polling_urls = {f"http://{control_ip}:8000/simulation/monitor": None for control_ip in running_request_data}
            polling_results = await send_multiple_get_request(polling_urls, {})
            current_directory = os.getcwd()
            if not os.path.exists(f"./{data_location}"):
                new_directory_path = os.path.join(current_directory, data_location)
                os.makedirs(new_directory_path)
            for result in polling_results:
                # print(result)
                if issubclass(type(result), Exception):
                    pass
                else:
                    ip = str(result[1]).split(":")[1][2:]
                    simulation_data[ip] = result[0]
            simulation.simulation_data = simulation_data
        if simulation.state == "running simulation":
            simulation.state = "finished"
        print(simulation.state_message, simulation.state)
network_info = {
        "testettst": {
        "is_target_ap": False,
        "aps": {
            "192.168.1.1": {
                "alias_name": "string",
                "tx_power": 18,
                "radio": "5G",
                "timeout": 300,
                "sever_types": [
                    "deterministic"
                ]
            },
        },
        "clients": {
            "192.168.1.2": {
                "simulation_type": "deterministic",
                "timeout": 300,
                "average_interval_time": 10,
                "average_packet_size": 128,
                "alias_name": "string"
            }
        }
    }
}

network_info2 = {
        "dlink-207A": {
        "is_target_ap": True,
        "aps": {},
        "clients": {
            "192.168.1.1": {
                "simulation_type": "deterministic",
                "timeout": 10,
                "average_interval_time": 2,
                "average_packet_size": 128,
                "alias_name": "string"
            }
        }
    }
}

class SIM:
    state = ""
    state_message = ""
    simulation_data = {}
sim = SIM()
if __name__ == "__main__":
    asyncio.run(simulation_tasks(sim, network_info2, "golfymarky", "5G", ""))   
    
# สายแลนด์หลุดหรือเครื่องดับจะค้างประมาณ 30 วินาที แล้วได้ ClientConnectorError 
# ถ้า process ระเบิดจะได้ ClientConnectorError เหมือนกัน แต่ message จะเป็น [The remote computer refused the network connection] แทน







async def is_wifi_connected_to_ssid(ssid: str):
    # Get a list of network interfaces
    interfaces = psutil.net_if_stats()
    # Check each interface to find the Wi-Fi connection
    for interface, stats in interfaces.items():
        if "Wi-Fi" in interface:
            if stats.isup:
                break   
            else:
                return False
    # print("snjhdkgemfdk")
    process = await asyncio.create_subprocess_shell(
        "netsh wlan show interfaces",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    lines = stdout.decode().split('\n')
    # print(lines)
    for line in lines:
        # print(line)
        if " SSID" in line:
            # print(line)
            ssid_now = line.split(":")[1].strip().strip("\r")
            # print(ssid_now)
        # print("ASDFFG")
    # print(ssid_now, ssid, ssid_now == ssid.strip())
    if ssid_now == ssid.strip():
        return True
    return False
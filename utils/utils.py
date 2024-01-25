from models.models import Scenario, Simulation, NodeConfiguration, NetworkModeEnum
from models.schemas import NodeConfigRequest
from typing import List
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
import asyncio, psutil, aiohttp, subprocess, time, json, os
    

def parse_network_from_node_config(node_configs: List[NodeConfiguration], target_ap_ssid: str) -> dict:
    enable_to_run = True
    network_info = {}
    warning_message = {}
    # find every ap in network and check if there are having ap
    for node in node_configs:
        if node.network_ssid not in network_info:
            network_info[node.network_ssid] = {
                "is_target_ap": node.network_ssid == target_ap_ssid,
                "aps": {},
                "clients": {}
            }
        if node.network_mode == NetworkModeEnum.ap:
            network_info[node.network_ssid]["aps"][node.control_ip_addr] = {
                "alias_name": node.alias_name,
                "tx_power": node.tx_power if node.tx_power is not None else 20,
                "radio": node.radio if node.radio is not None else "5G",
                "timeout": 0 if len(network_info[node.network_ssid]["clients"]) == 0 else max([network_info[node.network_ssid]["clients"][client]["timeout"] for client in network_info[node.network_ssid]["clients"]]),
                "sever_types": [] if len(network_info[node.network_ssid]["clients"]) == 0 else list({network_info[node.network_ssid]["clients"][client]["simulation_type"] for client in network_info[node.network_ssid]["clients"]})
            }
        else:
            network_info[node.network_ssid]["clients"][node.control_ip_addr] = dict(node.simulation_detail).copy()
            network_info[node.network_ssid]["clients"][node.control_ip_addr]["alias_name"] = node.alias_name
            # update ap ones
            for ap_ip in network_info[node.network_ssid]["aps"]:
                network_info[node.network_ssid]["aps"][ap_ip]["timeout"] = max(
                    network_info[node.network_ssid]["aps"][ap_ip]["timeout"],
                    network_info[node.network_ssid]["clients"][node.control_ip_addr]["timeout"]
                )
                if network_info[node.network_ssid]["clients"][node.control_ip_addr]["simulation_type"] not in network_info[node.network_ssid]["aps"][ap_ip]["sever_types"]:
                    network_info[node.network_ssid]["aps"][ap_ip]["sever_types"].append(network_info[node.network_ssid]["clients"][node.control_ip_addr]["simulation_type"])
    # find warning:
    #   1. have multiple aps in same ssid
    #   2. not having ap and that ssid is not the target_ap
    if len(network_info) == 0:
        enable_to_run = False
    for ssid in network_info:
        if not network_info[ssid]["is_target_ap"] and len(network_info[ssid]["aps"]) == 0:
            enable_to_run = False
            if ssid not in warning_message:
                warning_message[ssid] = []
            warning_message[ssid].append(f"there aren't any ap exist in this network")
        if len(network_info[ssid]["aps"]) > 1:
            enable_to_run = False
            if ssid not in warning_message:
                warning_message[ssid] = []
            warning_message[ssid].append(f"there are multiple aps exist in this network, include {network_info[ssid]['aps'].keys()}")
    return {
        "enable_to_run": enable_to_run,
        "warning_message": warning_message,
        "network_info": network_info 
    }

    {
        "ap_2.4G_a": {
            "is_target_ap": False,
            "aps": {
                "192.168.0.2": {
                    "alias_name": "...",
                    "timeout": "...",
                    "sever_types": ["real", "web", "file"],
                }
            },
            "clients": {
                "192.168.0.1": {
                    "alias_name": "...",
                    "timeout": "...",
                    "...": "...",
                }
            }
        },
        
    }

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

def _generate_script_for_run_ap_simulation(alias_name: str, mode, timeout):
    if mode == "deterministic":
        tmp_file = f"udp_server_{str(time.time()).replace('.', '_')}.json"
        return f"python -u ./simulation/server/udp_window_deterministic.py {alias_name} {timeout} {tmp_file}", tmp_file
    return None, None
def generate_scripts_for_run_simulation(scenario_mode, timeout):
    scripts = []; tmp_files = []
    for mode in scenario_mode:
        script, file_name = _generate_script_for_run_ap_simulation("this_device", mode, timeout)
        if script:
            scripts.append(script)
        if file_name:
            tmp_files.append(file_name)
    return scripts, tmp_files


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
    
async def keep_sending_post_request_until_all_ok(db_session: AsyncSession, simulation: Simulation, map_url_data: dict,  map_ip_to_alias_name: dict, update_exception_to_state: bool = True):
    ok_url = set() # set of url that already recieve 200 status response
    while True:
        tasks = [post_request(url, map_url_data[url]) for url in map_url_data if url not in ok_url]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if issubclass(type(result), Exception):
                if result is asyncio.CancelledError:
                    raise result
                # print(result, type(result.args), type(result.args[0]), (result.args[0]).host)
                # aiohttp.client_reqrep.ConnectionKey
                if update_exception_to_state:
                    if type(result.args[0]) is aiohttp.client_reqrep.ConnectionKey:
                        simulation.state_message += f"{map_ip_to_alias_name[result.args[0].host]} {time.time()}: {str(result)}\n"
                    else:
                        print(result, type(result.args), result.args)
                        print(type(result.args[0]), result.args[0])
                        simulation.state_message += str(result)+"\n"
            else:
                ok_url.add(result[1])
                simulation.state_message += f"{map_ip_to_alias_name[result[1].split(':')[1][2:]]} {time.time()}: {result[0]}\n"
        # commit (once per loop)
        db_session.add(simulation)
        await db_session.commit()
        if len(map_url_data) == len(ok_url):
            break
        await asyncio.sleep(2)

                
async def send_multiple_get_request(urls: dict, except_urls: set):
   tasks = [get_request(url, urls[url]) for url in urls if url not in except_urls]
   results = await asyncio.gather(*tasks, return_exceptions=True)
   return results

def read_json_file_and_delete_file(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        os.remove(file_path)
        return data
    except FileNotFoundError:
        print(f"The file {file_path} does not exist.")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON in {file_path}. Please check the file format.")
        return None


# (RequestInfo(
#     url=URL('http://192.168.1.1:8000/configure/client'), 
#     method='POST', 
#     headers=<CIMultiDictProxy('Host': '192.168.1.1:8000', 'Content-Type': 'application/json', 'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate', 'User-Agent': 'Python/3.11 aiohttp/3.9.1', 'Content-Length': '93')>, 
#     real_url=URL('http://192.168.1.1:8000/configure/client')), ()
#  )
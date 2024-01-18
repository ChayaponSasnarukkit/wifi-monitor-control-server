import asyncio
import signal, time, platform, sys
from asyncio.streams import StreamReader, StreamWriter
from typing import Coroutine

main_coroutine: Coroutine = None
alias_name = ""
timeout = 0

def handle_sigterm(*args):
    print("please out")
    sys.exit(0)

async def handle_client(reader: StreamReader, writer: StreamWriter):
    global alias_name
    global timeout
    sent_bytes = 0
    try:
        print(f"{alias_name} deterministic_server {time.time()}: client connected")
        # initial parameter
        # average_interval_time:00000 average_packet_size:0000000\n
        parameters = (await reader.readline()).decode('utf8').strip().split()

        # parsing the parameter
        average_interval_time = float(parameters[0][22:])/1000
        average_packet_size = int(parameters[1][20:])
        print(f"parametes: {average_interval_time} {average_packet_size}")
        
        # start simulation
        # start simulation
        while True:
            await asyncio.sleep(average_interval_time)
            data = "a"*(average_packet_size-1) + '\n'
            
            # writing data
            writer.write(data.encode('utf8'))
            await writer.drain()
            sent_bytes += average_packet_size
            
            # read from read buffer prevent it from begin full
            try:
                # wait for 0.1 msec (average_interval_time is in msec)
                request = (await asyncio.wait_for(reader.read(1024), timeout=0.001))
                # check for eof
                if not request:
                    print(f"{alias_name} deterministic_server {time.time()}: client has finished writing")
                    break
            except asyncio.TimeoutError:
                pass
    except asyncio.CancelledError:
        print(f"{alias_name} deterministic_server {time.time()}: task get cancelled")
    except Exception as e:
        print(f"{alias_name} deterministic_server {time.time()}: unexpected exception was raised when simulating {str(e)}")
        raise # raise after finish exec finally
    finally:
        print(sent_bytes)
        try:
            # # TODO: need to try if no writing eof can the other end recieve eof
            # print(f"{alias_name} deterministic_server {time.time()}: writing eof")
            # writer.write_eof()
            # await writer.drain()
            # if client has finished writing then closed socket
            print(f"{alias_name} deterministic_server {time.time()}: closing the socket")
            writer.close()
            await asyncio.wait_for(writer.wait_closed(), 10)
            print(f"{alias_name} deterministic_server {time.time()}: completely close")
        except asyncio.TimeoutError:
            print(f"{alias_name} deterministic_server {time.time()}: (writer.wait_closed() timeout: maybe the client is dead")
        except Exception as e:
            print(f"{alias_name} deterministic_server {time.time()}: unexpected exception was raised when trying to close gracefully {str(e)}")

async def run_server():
    server = await asyncio.start_server(handle_client, '0.0.0.0', 8888)
    print(f"{alias_name} deterministic_server {time.time()}: server start at 0.0.0.0:8888")
    if platform.system() == "Windows":
        # Register a signal handler for SIGINT
        # signal.signal(signal.SIGINT, handle_sigterm)
        pass
    else:
        pass
        # loop = asyncio.get_event_loop()
        # loop.add_signal_handler(signal.SIGINT, handle_sigterm)
    try:
        await asyncio.sleep(timeout)  # Wait for 5 minutes (300 seconds)
    except asyncio.CancelledError:
        print(f"{alias_name} deterministic_server {time.time()}: please PRINT this")
    finally:
        print(f"{alias_name} deterministic_server {time.time()}: Closing server socket.")
        server.close()
        await server.wait_closed()
        print(f"{alias_name} deterministic_server {time.time()}: Cancel all pending tasks(handle_client tasks) for exit.")
        tasks = [task for task in asyncio.all_tasks() if task is not
                asyncio.current_task()]
        list(map(lambda task: task.cancel(), tasks))
        print(f"Wait for all tasks to terminate: {[task.get_coro() for task in tasks]}")
        # await asyncio.gather(*tasks) # this will raise asyncio.exceptions.CancelledError if all tasks is cancelled
        await asyncio.gather(*tasks, return_exceptions=True)
        print(f"{alias_name} deterministic_server {time.time()}: All coroutines completed. Exiting.")

if __name__ == "__main__":
    
    # create the event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # signal.signal(signal.SIGTERM, handle_sigterm)
    try:
        # extract args
        "python -u ./simulation/server/deterministic.py {alias_name} {scenario.timeout}"
        alias_name, timeout = sys.argv[1], int(sys.argv[2])
        # create main_coroutine
        main_coroutine = run_server()
        # print(f"{alias_name} deterministic_server {time.time()}: finish running")
        print(f"{alias_name} deterministic_server {time.time()}: hello change from term to INT")
        # run main_coroutine until it complete
        loop.run_until_complete(main_coroutine)
    except KeyboardInterrupt:
        print(f"{alias_name} deterministic_server {time.time()}: INT INT INT INT \n\n\n")
    except Exception as e:
        print(str(e))
    finally:
        loop.close()
        print(f"{alias_name} deterministic_server {time.time()}: \n\nexited\n\n")

# server_process = subprocess.Popen(["c:\\Users\\hp\\AppData\\Local\\Programs\\Python\\Python310\\python.exe",  "-u",
#                                            "C:\\Users\\hp\\OneDrive\\Desktop\\final_project\\wifi_monitor_agents\\simulation\\server\\deterministic.py"],
#                                           shell=False,
#                                           stdin=subprocess.PIPE,
#                                           stdout=subprocess.PIPE,
#                                           stderr=subprocess.PIPE,
#                                           )

# server_process.terminate()
# stdout, stderr = server_process.communicate()
# server_process.returncode

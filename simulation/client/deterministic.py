import asyncio
import signal, sys, time, platform
from asyncio.streams import StreamReader, StreamWriter
from typing import Coroutine

main_coroutine: Coroutine = None
"python -u ./simulation/client/deterministic.py {alias_name} {scenario.timeout} {scenario.average_packet_size} {scenario.average_interval_time}"
server_ip = "192.168.2.1"
alias_name = ""
timeout = 0
average_packet_size = 64
average_interval_time = 1000

def handle_sigterm(*args):
    print(f"{alias_name} deterministic_client {time.time()}: SIGINT recieved")
    for task in asyncio.all_tasks():
        if task.get_coro() is main_coroutine and not task.cancelled():
            task.cancel()

async def simulate_client(reader: StreamReader, writer: StreamWriter):
    global server_ip
    global alias_name
    global timeout
    global average_packet_size
    global average_interval_time
    try:
        # initial parameter
        # average_interval_time:00000 average_packet_size:0000000\n
        need_to_send_parameter = f"average_interval_time:{str(average_interval_time).zfill(5)} average_packet_size:{str(average_packet_size).zfill(7)}\n"
        writer.write(need_to_send_parameter.encode())
        # sec => ms
        average_interval_time = average_interval_time/1000
        
        # start simulation 
        while True:
            await asyncio.sleep(average_interval_time)
            data = "a"*(average_packet_size-1) + '\n'
            
            # writing data
            writer.write(data.encode('utf8'))
            await writer.drain()
            
            # read from read buffer prevent it from begin full
            try:
                # wait for 0.1 msec (average_interval_time is in msec)
                request = (await asyncio.wait_for(reader.read(1024), timeout=0.001))
                # check for eof
                if not request:
                    print(f"{alias_name} deterministic_client {time.time()}: server has finished writing")
                    break
            except asyncio.TimeoutError:
                pass
    except asyncio.CancelledError:
        print(f"{alias_name} deterministic_client {time.time()}: task get cancelled")
    except Exception as e:
        print(f"{alias_name} deterministic_client {time.time()}: unexpected exception was raised when simulating: {str(e)}")
        raise # raise after finish exec finally
    finally:
        try:
            # print(f"{alias_name} deterministic_client {time.time()}: writing eof")
            # writer.write_eof()
            # await writer.drain()
            # if client has finished writing then closed socket
            print(f"{alias_name} deterministic_client {time.time()}: closing the socket")
            writer.close()
            await asyncio.wait_for(writer.wait_closed(), 10)
            print(f"{alias_name} deterministic_client {time.time()}: completely close")
        except asyncio.TimeoutError:
            print(f"{alias_name} deterministic_client {time.time()}: (writer.wait_closed() timeout: maybe the client is dead")
        except Exception as e:
            print(f"{alias_name} deterministic_client {time.time()}: unexpected exception was raised when trying to close gracefully: {str(e)}")

async def main():
    # create connection
    reader, writer = await asyncio.open_connection(server_ip, 8888)
    # schedule simulate_client task
    simulate_client_task = asyncio.create_task(simulate_client(reader, writer))
    # Register a signal handler for SIGINT
    if platform.system() == "Windows":
        # Register a signal handler for SIGINT
        # signal.signal(signal.SIGINT, handle_sigterm)
        pass
    else:
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, handle_sigterm)
    try:
        await asyncio.sleep(timeout) # wait for 300 sec
    except asyncio.CancelledError:
        pass
    finally:
        print(f"{alias_name} deterministic_client {time.time()}: timeout terminate the simulate_client task")
        simulate_client_task.cancel()
        await simulate_client_task
        
        
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # extract argument here
        alias_name, timeout, average_packet_size, average_interval_time = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
        if len(sys.argv) == 6:
            server_ip = sys.argv[5]
        # create main_coroutine
        main_coroutine = main()
        print(f"{alias_name} deterministic_client {time.time()}: hello change from term to INT")
        # run main_coroutine until it complete
        loop.run_until_complete(main_coroutine)
    except KeyboardInterrupt:
        print(f"{alias_name} deterministic_client {time.time()}: INT INT INT INT \n\n\n")
    except Exception as e:
        print(e)
    finally:
        loop.close()
        print(f"{alias_name} deterministic_client {time.time()}: \n\nexited\n\n")

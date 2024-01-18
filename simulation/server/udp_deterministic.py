import select
import socket, asyncio, time

client_sockets = {}
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(("0.0.0.0", 8888))
server_socket.setblocking(0)

def _is_initial_message(data):
    print(len(data))
    if data.find("average_interval_time:")!=-1 and data.find("average_packet_size:") and len(data)==56:
        print("True")
        return True
    else:
        return False

# case 1: exception while sending ack 
#         keep sending parameters to server but no response
# case 2: exception while simulating
#         task died but socket is not closing the data will fwd to the socket but no one read it until it full
#         the other end will keep sending until write buffer is full too
# fixed case 1 by close socket with finally so that the main() can create new client_handler task
# but will have problem with case 2 because the message will be flooded to server_socket
async def client_handler(client_socket, data, alias_name, addr, timeout):
    try:
        # sending ack (making 3 way handshake)
        state = "sending ack"
        while True:
            _, writable, _ = select.select([], [client_socket], [], 0)
            print("writable: ", writable)
            if writable:
                client_socket.send(b"parameters recieved")
            # wait before sending other ack
            await asyncio.sleep(1)
            readable, _, _ = select.select([client_socket], [], [], 0)
            print("readable: ", readable)
            if readable:
                message = client_socket.recv(1024)
                if message.decode() == "ack recieved, ready to simulate":
                    state = "handshaked"
                    break
        # finish handshaking
        # start simulation
        # parsing the parameter
        parameters = data.strip().split()
        average_interval_time = float(parameters[0][22:])/1000
        average_packet_size = int(parameters[1][20:])
        
        send_data = ("a"*(average_packet_size-1) + '\n').encode()
        sent_bytes = 0
        recv_bytes = 0
        check_point = int((timeout/average_interval_time)/10)
        loop_cnt = 0
        while True:
            readable, writable, _ = select.select([client_socket], [client_socket], [], 0)
            if readable:
                test = client_socket.recv(average_packet_size)
                recv_bytes += len(test)
            if writable:
                client_socket.send(send_data)
                sent_bytes += average_packet_size
                if loop_cnt%check_point == 0 :
                    print(f"{sent_bytes} bytes was sent to client")
            elif loop_cnt%check_point == 0 :
                print(f"{sent_bytes} bytes was sent to client before it full, but now write buffer is full")
            loop_cnt += 1
            await asyncio.sleep(average_interval_time)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"{alias_name} deterministic_server {time.time()}: unexpected exception occured in {addr} handler_client task {str(e)}")
    

async def main(timeout, alias_name):
    try:
        end_time = timeout + time.time()
        while time.time() < end_time:
            readable, _, _ = select.select([server_socket], [], [], 0)
            # read until it no more readable in this socket then sleep
            # because it has long sleep time
            while readable:
                data, addr = server_socket.recvfrom(1024)
                if _is_initial_message(data.decode()) and addr not in client_sockets:
                    # create new client socket for long communication
                    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    client_socket.bind(("0.0.0.0", 8888))
                    client_socket.connect(addr)
                    client_socket.setblocking(0)
                    client_sockets[addr] = client_socket
                    # create task for handler
                    asyncio.create_task(client_handler(client_socket, data, alias_name, addr, timeout))
                # update readable
                readable, _, _ = select.select([server_socket], [], [], 0)
            
            await asyncio.sleep(1)
        print("timeout")
    except asyncio.CancelledError:
        print("cancel signal was recieved")
        raise
    except Exception as e:
        print(f"{alias_name} deterministic_server {time.time()}: unexpected exception occured {str(e)}")
    finally:
        tasks = [task for task in asyncio.all_tasks() if task is not
                asyncio.current_task()]
        list(map(lambda task: task.cancel(), tasks))
        print(f"Wait for all tasks to terminate: {[task.get_coro() for task in tasks]}")
        # await asyncio.gather(*tasks) # this will raise asyncio.exceptions.CancelledError if all tasks is cancelled
        await asyncio.gather(*tasks, return_exceptions=True)
        print(f"closing all opened sockets")
        server_socket.close()
        for addr in client_sockets:
            client_sockets[addr].close()
        print(f"all sockets has been closed [the package sent after this will get the exception about port unreacheble]")
        
if __name__ == "__main__":
    asyncio.run(main(60, "test_server"))
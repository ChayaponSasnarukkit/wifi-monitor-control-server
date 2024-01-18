import select
import socket, asyncio, time

async def client_handler(client_socket,average_interval_time, average_packet_size , alias_name, addr, timeout):
    try:
        # sending ack (making 3 way handshake)
        need_to_send_parameter = f"average_interval_time:{str(average_interval_time).zfill(5)} average_packet_size:{str(average_packet_size).zfill(7)}\n"
        state = "sending params"
        while True:
            try:
                _, writable, _ = select.select([], [client_socket], [], 0)
                print("writable: ", writable)
                if writable:
                        client_socket.send(need_to_send_parameter.encode())
                # wait before sending other ack
                await asyncio.sleep(1)
                readable, _, _ = select.select([client_socket], [], [], 0)
                print("readable: ", readable)
                if readable:
                    message = client_socket.recv(1024)
                    if message.decode() == "parameters recieved":
                        state = "sending ack"
                        break
            except socket.error as e:
                print(str(e))
        print("state ", state)
        while True:
            try:
                _, writable, _ = select.select([], [client_socket], [], 0)
                if writable:
                    client_socket.send("ack recieved, ready to simulate".encode())
                await asyncio.sleep(1)
                readable, _, _ = select.select([client_socket], [], [], 0)
                if readable:
                    print(message)
                    message = client_socket.recv(1024)
                    if message.decode() != "parameters recieved":
                        state = "handshaked"
                        break
            except socket.error as e:
                print(str(e))

        average_interval_time = average_interval_time/1000
        
        send_data = ("a"*(average_packet_size-1) + '\n').encode()
        sent_bytes = 0
        recv_bytes = 0
        check_point = int((timeout/average_interval_time)/10)
        print(check_point, timeout, average_interval_time)
        loop_cnt = 0
        while True:
            # print(time.time())
            readable, writable, _ = select.select([client_socket], [client_socket], [], 0)
            # print("writable: ", writable)
            # print("readable: ", readable)
            # print(loop_cnt)
            while readable:
                test = client_socket.recv(average_packet_size)
                recv_bytes += len(test)
                readable, _, _ = select.select([client_socket], [], [], 0)
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
        print(f"{alias_name} deterministic_server {time.time()}:  {addr} handler_client task terminated")
    finally:
        print(sent_bytes, "  ", recv_bytes)

async def main():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client_socket.bind(("192.168.103.50", 0))
    client_socket.connect(("192.168.103.226", 8888))
    client_socket.setblocking(0)
    task = asyncio.create_task(client_handler(client_socket, 1, 128, "test_client", "(127.0.0.1, someport)", 60))
    try: 
        await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass
    finally:
        print(f"test_client deterministic_client {time.time()}: timeout terminate the simulate_client task")
        task.cancel()
        await task
        client_socket.close()
        

if __name__ == "__main__":
    asyncio.run(main())
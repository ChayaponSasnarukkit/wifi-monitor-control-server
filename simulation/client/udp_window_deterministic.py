import select, sys, json
import socket, asyncio, time

timeout = 60
average_packet_size = 128
average_interval_time = 1
alias_name = "testets"
control_ip = "192.168.1.2"
absolute_path = f"../udp_{str(time.time()).replace('.', '_')}.txt"

server_addr = ("192.168.2.1", 8888)
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# template
# template_log = "{alias_name} {time} deterministic: {message}"
template_log = "{} {} deterministic: {}"
# dictionary map address to tuple of parameters(next_send [arrival_time], message [size])
parameters = {}
# dictionary map address to state of its operation
states = {}
# dictionary that collect error message wait for being print out
error_log = {}
recv_bytes = {}
send_bytes = {}
monitor_data = []

def parsing_header_information(data, addr, read_timestamp):
    # [str(0).zfill(7).encode(), f"{time.time():.7f}".encode(), ((average_packet_size-25)*"a").encode()]
    global monitor_data; global parameters
    try:
        if data is None or addr is None:
            return
        seq_number = int(data[:7])
        send_timestamp = float(data[7:25])
        read_timestamp = time.time()
        diff = read_timestamp - send_timestamp
        # print(diff, send_timestamp, read_timestamp, data[:30])
        monitor_data.append([read_timestamp, seq_number, (send_timestamp, diff, len(data))])
    except ValueError:
        pass

# ไปทำที่ control แล้วโยนเข้ามาดีกว่า
# def _get_ip_addr(interface):
#     if "Windows" in platform.platform():
#         result = subprocess.run(["ipconfig"], capture_output=True, text=True)
#         ipconfig_output = result.stdout
#     else:
#         result = subprocess.run(["ipconfig"], capture_output=True, text=True)
#         ipconfig_output = result.stdout

    
def recv_from(buf_size):
    global parameters; global timeout; global alias_name; global template_log; global states
    global error_log; global recv_bytes; global send_bytes
    # print("try to recv")
    try:
        data, addr = client_socket.recvfrom(buf_size)
        # print("data", data)
        data = data.decode()
        if addr not in recv_bytes:
            recv_bytes[addr] = 0
        recv_bytes[addr] += len(data)
        return data, addr
    except socket.error as e:
        # print("exc")
        # err_message = f"from {addr} when trying to read socket \"{str(e)}\" has occured"
        err_message = f"when trying to read socket \"{str(e)}\" has occured"
        # print(e.errno, e.args)
        if err_message in error_log:
            error_log[err_message].append(time.time())
        else:
            error_log[err_message] = [time.time()]
            print(template_log.format(alias_name, time.time(), err_message))
        return None, None
        # if e.errno == 10054:
        #     states[addr] = "stop writing"
        
def send_to(data, addr):
    global parameters; global timeout; global alias_name; global template_log; global states
    global error_log; global recv_bytes; global send_bytes
    _, writable, _ = select.select([], [client_socket], [], 0)
    if not writable:
        err_message = f"write buffer is full, can't writer data to socket"
        if err_message in error_log:
            error_log[err_message].append(time.time())
        else:
            error_log[err_message] = [time.time()]
            print(template_log.format(alias_name, time.time(), err_message))
        return -1
    try:
        client_socket.sendto(data, addr)
        if addr not in send_bytes:
            send_bytes[addr] = 0
        send_bytes[addr] += len(data)
        return 0
    except socket.error as e:
        err_message = f"from {addr} when trying to write socket \"{str(e)}\" has occured"
        if err_message in error_log:
            error_log[err_message].append(time.time())
        else:
            error_log[err_message] = [time.time()]
            print(template_log.format(alias_name, time.time(), err_message))
        return 1

def main():
    global parameters; global timeout; global alias_name; global template_log; global states; server_addr; control_ip; global absolute_path
    global error_log; global recv_bytes; global send_bytes; global average_interval_time; global average_packet_size
    try:
        start_time = time.time()
        next_time = start_time
        check_point = start_time + 30
        end_time = start_time + timeout
        state = "handshaking"
        seq_number = 0
        need_to_send_parameter = (f"average_interval_time:{str(average_interval_time).zfill(5)} average_packet_size:{str(average_packet_size).zfill(7)} control_ip:{control_ip}\n").encode()
        # message => 0000001 1706027203.7130814 dump"a" (7+18=25 dump_a = avergae-25)
        message = [str(seq_number).zfill(7).encode, f"{time.time():.7f}".encode(), ((average_packet_size-25)*"a").encode()]
        interval_time_sec = average_interval_time/1000
        # sending parameters
        send_to(need_to_send_parameter, server_addr)
        last_time = time.time()
        while time.time() < end_time:
            while state != "handshaked":
                try:
                    # sending the initial message
                    if time.time()-last_time >= 1:
                        print(time.time()-last_time)
                        send_to(need_to_send_parameter, server_addr)
                        last_time = time.time()
                        log_message = f"parameters sent to {server_addr}, waiting for ack packet"
                        print(template_log.format(alias_name, time.time(), log_message))
                    # keep sending every 1 sec until ack packet was recieved
                    readable, _, _ = select.select([client_socket], [], [], 0)
                    if readable:
                        data, _ = recv_from(1024)
                        if data and data == "parameters recieved":
                            log_message = f"ack packet recieved, start sending simulate packet"
                            print(template_log.format(alias_name, time.time(), log_message))
                            state = "handshaked"
                            break
                except socket.error as e:
                    print(template_log.format(alias_name, time.time(), str(e)))
            # read socket until no data available to read
            readable, _, _ = select.select([client_socket], [], [], 0)
            # print(readable)
            if readable:
                read_timestamp = time.time()
                data, addr = recv_from(1024)
                parsing_header_information(data, addr, read_timestamp)
                
            now = time.time()
            if now >= next_time:
                message[0] = str(seq_number).zfill(7).encode()
                message[1] = f"{time.time():.7f}".encode()
                return_code = send_to(b"".join(message), server_addr)
                if return_code != -1:
                    next_time = now + interval_time_sec
                    seq_number += 1
            
            # แสดง log ที่เก็บไว้ทุกๆ 30 วินาที
            now = time.time()
            if now >= check_point:
                for addr in recv_bytes:
                    print(template_log.format(alias_name, time.time(), f"{recv_bytes[addr]} bytes recv from {addr}"))
                for addr in send_bytes:
                    print(template_log.format(alias_name, time.time(), f"{send_bytes[addr]} bytes send to {addr}"))
                for error in error_log:
                    # print(template_log.format(alias_name, time.time(), f"\"{error}\" occured more {len(error_log[error])} times at {error_log[error]}"))
                    print(template_log.format(alias_name, time.time(), f"\"{error}\" occured more {len(error_log[error])} times"))
                    error_log[error] = []
                check_point += 30
    # except Exception as e:
    #     print(template_log.format(alias_name, time.time(), f"unexpected exception \"{str(e)}\" has occured"))
    finally:
        for addr in recv_bytes:
            print(template_log.format(alias_name, time.time(), f"{recv_bytes[addr]} bytes recv from {addr}"))
        for addr in send_bytes:
            print(template_log.format(alias_name, time.time(), f"{send_bytes[addr]} bytes send to {addr}"))
        print(template_log.format(alias_name, time.time(), f"closing the socket"))
        client_socket.close()
        with open(absolute_path, "w") as f:
            json.dump({"udp_deterministic_server_data_monitored_from_client": monitor_data}, f)
        print(template_log.format(alias_name, time.time(), f"socket has been closed, program exited"))
        
if __name__ == "__main__":
    try:
        alias_name, timeout, average_packet_size, average_interval_time, absolute_path, control_ip = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6]
        if len(sys.argv) == 8:
            server_ip = sys.argv[7]
            server_addr = (server_ip, 8888)
    except:
        pass
    client_socket.connect(server_addr)
    client_socket.setblocking(0)
    main()
    
# python C:\Users\hp\OneDrive\Desktop\final_project\wifi_monitor_agents\simulation\client\udp_window_deterministic.py test 5 1024 1 C:\Users\hp\OneDrive\Desktop\final_project\wifi_monitor_agents\simulation\client\tmptmp.txt 192.168.1.1 127.0.0.1
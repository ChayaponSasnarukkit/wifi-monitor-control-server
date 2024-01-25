import select, sys
import socket, asyncio, time, json

client_sockets = {}
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(("0.0.0.0", 8888))
server_socket.setblocking(0)

timeout = 60
alias_name = "testets"
# template
# template_log = "{alias_name} {time} deterministic: {message}"
template_log = "{} {} deterministic: {}"
# dictionary map address to tuple of parameters(next_send [arrival_time], message [size], seq_number)
parameters = {}
# dictionary map address to state of its operation
states = {}
# dictionary that collect error message wait for being print out
error_log = {}
recv_bytes = {}
send_bytes = {}
absolute_path = ""
# data map from ip_addr 
monitor_data = {}

def _is_initial_message(data):
    # print(len(data))
    if data and data.find("average_interval_time:")!=-1 and data.find("average_packet_size:")!=-1 and data.find("control_ip:")!=-1:
        # print("True")
        return True
    else:
        return False

def parsing_header_information(data, addr, read_timestamp):
    # [str(0).zfill(7).encode(), f"{time.time():.7f}".encode(), ((average_packet_size-25)*"a").encode()]
    global monitor_data; global parameters
    try:
        # print(data, addr)
        seq_number = int(data[:7])
        send_timestamp = float(data[7:25])
        diff = read_timestamp - send_timestamp
        # print(diff, send_timestamp, read_timestamp, data[:30])
        control_ip = parameters[addr]["control_ip"]
        if control_ip not in monitor_data:
            monitor_data[control_ip] = []
            # print(control_ip)
        monitor_data[control_ip].append([read_timestamp, seq_number, (send_timestamp, diff, len(data))])
        # print(monitor_data)
    except ValueError as e:
        print(e.args)
        pass

def recv_from(buf_size):
    global parameters; global timeout; global alias_name; global template_log; global states
    global error_log; global recv_bytes; global send_bytes
    # print("try to recv")
    try:
        data, addr = server_socket.recvfrom(buf_size)
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
    global parameters; global timeout; global alias_name; global template_log; global states; global absolute_path
    global error_log; global recv_bytes; global send_bytes
    _, writable, _ = select.select([], [server_socket], [], 0)
    if not writable:
        err_message = f"write buffer is full, can't writer data to socket"
        if err_message in error_log:
            error_log[err_message].append(time.time())
        else:
            error_log[err_message] = [time.time()]
            print(template_log.format(alias_name, time.time(), err_message))
        return -1
    try:
        server_socket.sendto(data, addr)
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
    global parameters; global timeout; global alias_name; global template_log; global states; global absolute_path
    global error_log; global recv_bytes; global send_bytes
    try:
        start_time = time.time()
        check_point = start_time + 30
        end_time = start_time + timeout
        while time.time() < end_time:
            # read socket until no data available to read
            readable, _, _ = select.select([server_socket], [], [], 0)
            # print(readable)
            while readable:
                # NOTE QUESTION: ใช้ขนาด buffer เท่าไหร่ดี แต่ play save ก็ 65535 ไม่เกินแต่มันจะพังมั้ยไม่มั่นใจ
                #               (ไม่มั่นใจว่าถ้า buffer ที่ใส่ให้เล็กกว่า message จริงอ่านรอบหน้าจะเป็นยังไง คิดว่าน่าจะยังจะอ่าน message เดิม)
                # time stamp after select return that there are packet in buffer
                read_timestamp = time.time()
                data, addr = recv_from(1024)
                if addr not in states:
                    if _is_initial_message(data):
                        # parse the params
                        local_parameters = data.strip().split()
                        average_interval_time = float(local_parameters[0][22:])/1000
                        average_packet_size = int(local_parameters[1][20:])
                        control_ip = local_parameters[2][11:]
                        print(average_interval_time, " ", average_packet_size, " ", control_ip)
                        # modify global state
                        parameters[addr] = {}
                        parameters[addr]["interval_time"] = average_interval_time
                        parameters[addr]["next_time"] = time.time() + average_interval_time
                        parameters[addr]["control_ip"] = control_ip
                        parameters[addr]["seq_number"] = 0
                        parameters[addr]["message"] = [str(0).zfill(7).encode(), f"{time.time():.7f}".encode(), ((average_packet_size-25)*"a").encode()]
                        print(len(b"".join(parameters[addr]["message"])))
                        states[addr] = "handshaking"
                        # send ack packet out
                        log_message = f"from {addr} parameters recieved, sending ack packet"
                        print(template_log.format(alias_name, time.time(), log_message))
                        send_to(b"parameters recieved", addr)
                elif states[addr] == "handshaking":
                    # if client keep sending initial message => it mean it doesn't recieve ack packet
                    if _is_initial_message(data):
                        # send it again
                        send_to(b"parameters recieved", addr)
                    else:
                        # แปลว่าอีกฝั่งหนึ่งเริ่มส่ง simulate data แล้ว => แปลว่าได้รับ ack แล้ว
                        states[addr] = "handshaked"
                        log_message = f"from {addr} simulate packet recieved, start sending simulate packet"
                        print(template_log.format(alias_name, time.time(), log_message))
                        # recieve packet ที่เหลือ [ในกรณีที่ params มีขนาดแพ็คเก็ตที่ใหญ่กว่า 1024]
                        parsing_header_information(data, addr, read_timestamp)
                else:
                    # print(states[addr] == "handshaked")
                    # states[addr] == "handshaked" /////or states[addr] == "stop sending"
                    # ถ้า handshaked แล้ว recieve packet ที่เหลือ [ในกรณีที่ params มีขนาดแพ็คเก็ตที่ใหญ่กว่า 1024]
                    parsing_header_information(data, addr, read_timestamp)
                # update readable
                readable, _, _ = select.select([server_socket], [], [], 0)
                
            for addr in parameters:
                now = time.time()
                if now >= parameters[addr]["next_time"]:
                    parameters[addr]["message"][0] = str(parameters[addr]["seq_number"]).zfill(7).encode()
                    parameters[addr]["message"][1] = f"{time.time():.7f}".encode()
                    return_code = send_to(b"".join(parameters[addr]["message"]), addr)
                    if return_code == -1:
                    #     # -1 mean buffer is full, so no need to keep sending other out since it shared buffer
                        break
                    #     # break before update seq_number because they not sending out from beginning, this can cause by latency/datarate
                    #     # not counting as packet lost
                    parameters[addr]["next_time"] = now + parameters[addr]["interval_time"]
                    parameters[addr]["seq_number"] += 1
            
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
    except Exception as e:
        print(template_log.format(alias_name, time.time(), f"unexpected exception \"{str(e)}\" has occured"))
    finally:
        for addr in recv_bytes:
            print(template_log.format(alias_name, time.time(), f"{recv_bytes[addr]} bytes recv from {addr}"))
        for addr in send_bytes:
            print(template_log.format(alias_name, time.time(), f"{send_bytes[addr]} bytes send to {addr}"))
        print(template_log.format(alias_name, time.time(), f"closing the socket"))
        server_socket.close()
        with open(absolute_path, "w") as f:
            json.dump({"udp_deterministic_client_data_monitored_from_server": monitor_data}, f)
        print(template_log.format(alias_name, time.time(), f"socket has been closed, program exited"))
        
if __name__ == "__main__":
    "python -u ./simulation/server/udp_window_deterministic.py {alias_name} {scenario.timeout}"
    try:
        alias_name, timeout, absolute_path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    except:
        pass
    main()
    
    "python ./simulation/server/udp_window_deterministic.py test 60 ./simulation/server/udp_test1.json"
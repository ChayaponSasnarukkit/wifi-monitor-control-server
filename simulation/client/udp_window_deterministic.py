import select, sys
import socket, asyncio, time

timeout = 60
average_packet_size = 128
average_interval_time = 1
alias_name = "testets"

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

def _is_initial_message(data):
    print(len(data))
    if data.find("average_interval_time:")!=-1 and data.find("average_packet_size:") and len(data)==56:
        print("True")
        return True
    else:
        return False
    
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
        return
    try:
        client_socket.sendto(data, addr)
        if addr not in send_bytes:
            send_bytes[addr] = 0
        send_bytes[addr] += len(data)
    except socket.error as e:
        err_message = f"from {addr} when trying to write socket \"{str(e)}\" has occured"
        if err_message in error_log:
            error_log[err_message].append(time.time())
        else:
            error_log[err_message] = [time.time()]
            print(template_log.format(alias_name, time.time(), err_message))

def main():
    global parameters; global timeout; global alias_name; global template_log; global states; server_addr
    global error_log; global recv_bytes; global send_bytes; global average_interval_time; global average_packet_size
    try:
        start_time = time.time()
        next_time = start_time
        check_point = start_time + 30
        end_time = start_time + timeout
        state = "handshaking"
        need_to_send_parameter = (f"average_interval_time:{str(average_interval_time).zfill(5)} average_packet_size:{str(average_packet_size).zfill(7)}\n").encode()
        message = (average_packet_size*"a").encode()
        interval_time_sec = average_interval_time/1000
        while time.time() < end_time:
            # sending parameters
            while state != "handshaked":
                try:
                    # sending the initial message
                    send_to(need_to_send_parameter, server_addr)
                    log_message = f"parameters sent to {server_addr}, waiting for ack packet"
                    print(template_log.format(alias_name, time.time(), log_message))
                    # keep sending every 1 sec until ack packet was recieved
                    time.sleep(1)
                    readable, _, _ = select.select([client_socket], [], [], 0)
                    if readable:
                        data, _ = recv_from(1024)
                        if data and data == "parameters recieved":
                            log_message = f"ack packet recieved, start sending simulate packet"
                            print(template_log.format(alias_name, time.time(), log_message))
                            state = "handshaked"
                            break
                except socket.error as e:
                    print(str(e))
            # read socket until no data available to read
            readable, _, _ = select.select([client_socket], [], [], 0)
            # print(readable)
            if readable:
                data, addr = recv_from(average_packet_size)
                
            now = time.time()
            if now >= next_time:
                send_to(message, server_addr)
                next_time = now + interval_time_sec
            
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
        print(template_log.format(alias_name, time.time(), f"socket has been closed, program exited"))
        
if __name__ == "__main__":
    try:
        alias_name, timeout, average_packet_size, average_interval_time = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
        if len(sys.argv) == 6:
            server_ip = sys.argv[5]
            server_addr = (server_ip, 8888)
    except:
        pass
    client_socket.connect(server_addr)
    client_socket.setblocking(0)
    main()
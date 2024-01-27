import random, sys, requests, time, json

server_ip = "192.168.2.1"
base_url = f"http://{server_ip}:8088"
timeout = 60
average_packet_size = 1000 # 1 kB
# average time between click in second
average_interval_time = 2000/1000 # average 2 second between click
template_log = "{} {} web_application: {}"
absolute_path = f"../../web_{str(time.time()).replace('.', '_')}.txt"
total_requests = 0
total_bytes = 0

def main():
    try:
        global total_bytes; global total_requests; global absolute_path
        global base_url; global alias_name; global average_packet_size; global average_interval_time; global timeout
        average_data_rates = []
        check_point = time.time() + 30
        end_time = time.time() + timeout
        lambda_size = 1/average_packet_size
        lambda_time = 1/average_interval_time
        print(template_log.format(alias_name, time.time(), f"process has started"))
        while time.time() < end_time:
            try:
                # random packet size
                if total_requests%100000 == 0:
                    interval_times = [random.expovariate(lambda_time) for _ in range(100000)]
                    packet_sizes = [random.expovariate(lambda_size) for _ in range(100000)]
                packet_size = int(packet_sizes[total_requests%100000])
                # get timestamp before send request
                start_requests = time.time()
                # sent request for string that have size equal to packet size
                res = requests.get(f"{base_url}/sim_api/{packet_size}")
                # get timestamp when finish recieving
                finish_recieve = time.time()
                # get server timestamp 
                # server_start_response = float(res[:18])
                # append average data rate
                average_data_rates.append([finish_recieve, len(res.content), start_requests])
                total_requests += 1; total_bytes += len(res.content)
                if time.time() >= check_point:
                    print(template_log.format(alias_name, time.time(), f"{total_requests} requests sent, {total_bytes} bytes recv from {base_url}"))
                    check_point += 30
                # sleep => simulate the user read the page
                time.sleep(interval_times[(total_requests-1)%100000])
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print((template_log.format(alias_name, time.time(), f"Exception {str(e)} occured from {base_url}")))
    except KeyboardInterrupt:
        pass
    finally:
        with open(absolute_path, "w") as f:
            json.dump({"web_average_data_rates": average_data_rates}, f)
        print(template_log.format(alias_name, time.time(), f"program EXIT with {total_requests} requests sent, {total_bytes} bytes recv from {base_url}"))    

if __name__ == "__main__":
    try:
        alias_name, timeout, average_packet_size, average_interval_time, absolute_path = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])/1000, sys.argv[5]
        if len(sys.argv) == 7:
            server_ip = sys.argv[6]
            base_url = f"http://{server_ip}:8088"
    except:
        pass
    main()
    
    # python .\simulation\client\web_application.py a 60 1024 2000 web.txt 127.0.0.1
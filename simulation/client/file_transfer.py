import random, sys, requests, time, json

server_ip = "192.168.2.1"
base_url = f"http://{server_ip}:8080"
alias_name = ""
average_file_size = 10000000
file_size_standard_deviation = 0.05*average_file_size
timeout = 60
absolute_path = f"../../file_{str(time.time()).replace('.', '_')}.txt"


def main():
    try:
        template_log = "{} {} file_transfer: {}"
        total_files = 0
        total_bytes = 0
        global base_url; global alias_name; global average_file_size; global file_size_standard_deviation; global timeout; global absolute_path
        print(template_log.format(alias_name, time.time(), f"process has started"))
        average_data_rates = []
        check_point = time.time() + 30
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                # print(time.time())
                # random file size
                if total_files%100000 == 0:
                    file_sizes = [int(random.normalvariate(average_file_size, file_size_standard_deviation)) for _ in range(100000)]
                file_size = file_sizes[total_files%100000]
                # get timestamp before send request
                start_requests = time.time()
                # sent request for string that have size equal to file size
                file = requests.get(f"{base_url}/downloadfilea/?size={file_size}")
                # get timestamp when finish recieving
                finish_recieve = time.time()
                # get server timestamp 
                server_start_response = float(file[:18])
                # append average data rate
                average_data_rates.append([finish_recieve, len(file.content), server_start_response])
                total_files += 1; total_bytes += len(file.content)
                now = time.time()
                if now >= check_point:
                    print(template_log.format(alias_name, time.time(), f"{total_files} files downloaded, {total_bytes} bytes recv from {base_url}"))
                    check_point += 30
                # print(file_size, file, len(file.content), file.content)
                # sleep => simulate the user read the page
                time.sleep(2)
                # print(time.time())
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print((template_log.format(alias_name, time.time(), f"Exception {str(e)} occured from {base_url}")))
    except KeyboardInterrupt:
        pass
    finally:
        with open(absolute_path, "w") as f:
            json.dump({"file_average_data_rates": average_data_rates}, f)
        print(template_log.format(alias_name, time.time(), f"program EXIT with {total_files} files downloaded, {total_bytes} bytes recv from {base_url}"))
        

if __name__ == "__main__":
    try:
        alias_name, timeout, average_file_size, absolute_path = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
        if len(sys.argv) == 6:
            server_ip = sys.argv[5]
            base_url = f"http://{server_ip}:8080"
        file_size_standard_deviation = 0.05*average_file_size
    except:
        pass
    main()
    
    # python C:\Users\hp\OneDrive\Desktop\final_project\wifi-monitor-control-server\simulation\client\file_transfer.py test 60 1000000 127.0.0.1
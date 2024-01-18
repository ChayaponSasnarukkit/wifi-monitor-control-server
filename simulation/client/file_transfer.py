import numpy as np
import random, sys, requests, time

server_ip = "192.168.2.1"
base_url = f"http://{server_ip}:8080"
alias_name = ""
average_file_size = 10000000
file_size_standard_deviation = 0.05*average_file_size
timeout = 60


def main():
    try:
        template_log = "{} {} file_transfer: {}"
        total_files = 0
        total_bytes = 0
        global base_url; global alias_name; global average_file_size; global file_size_standard_deviation; global timeout
        check_point = time.time() + 30
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                # print(time.time())
                # random file size
                file_size = int(np.random.normal(average_file_size, file_size_standard_deviation))
                # sent request for string that have size equal to file size
                file = requests.get(f"{base_url}/downloadfilea/?size={file_size}")
                total_files += 1; total_bytes += len(file.content)
                now = time.time()
                if now >= check_point:
                    print(template_log.format(alias_name, time.time(), f"{total_files} files downloaded, {total_bytes} bytes recv from {base_url}"))
                    check_point += 30
                # print(file_size, file, len(file.content), file.content)
                # sleep => simulate the user read the page
                time.sleep(2)
                # print(time.time())
            except Exception as e:
                print((template_log.format(alias_name, time.time(), f"Exception {str(e)} occured from {base_url}")))
                break
    except KeyboardInterrupt:
        pass
    finally:
        print(template_log.format(alias_name, time.time(), f"program EXIT with {total_files} files downloaded, {total_bytes} bytes recv from {base_url}"))
        

if __name__ == "__main__":
    try:
        alias_name, timeout, average_file_size = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
        if len(sys.argv) == 5:
            server_ip = sys.argv[4]
            base_url = f"http://{server_ip}:8080"
        file_size_standard_deviation = 0.05*average_file_size
    except:
        pass
    main()
    
    # python C:\Users\hp\OneDrive\Desktop\final_project\wifi-monitor-control-server\simulation\client\file_transfer.py test 60 1000000 127.0.0.1
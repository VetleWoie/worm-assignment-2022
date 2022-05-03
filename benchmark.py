import requests
import time
import json

import argparse
import sys
import os
import signal
import subprocess

file="hostslist"
executable = "./worm.bin"
wormport = "64210"

def get_available_nodes(n):
    return subprocess.check_output(['/share/apps/ifi/available-nodes.sh']).decode().splitlines()[:n]

def write_to_node_file(n, port):
    nodes = get_available_nodes(n)
    a = [f"{node}:{port}\n" for node in nodes]
    with open(file, "w") as f:
        for gate in a:
            f.write(gate)
    return [(node, port) for node in nodes]

def open_gates(n=20, port = 64209):
    gate_list = write_to_node_file(n, port)
    p = subprocess.run(f'cat {file} | ./worm_gate/wormgates_start.sh', shell=True)
    return gate_list

def spawn_worm(gate):
        with open(executable,"rb") as exe:
            exe = exe.read()
        # url = "http://{gate[0]}:{gate[1]}/worm_entrance?args={gate[0]}:{gate[1]}&args={self.max_worms}"
        r = requests.post(f"http://{gate[0]}:{gate[1]}/worm_entrance?args={gate[0]}:{gate[1]}&args={1}", data=exe)

def benchmark_grow(start=1, stop=20, n=3):
    gate_list = open_gates(stop)
    #Upload one worm
    spawn_worm(gate_list[0])
    count_segment = 0
    leader_count = 0
    print("Starting benvchmark")
    data_list = []
    time.sleep(1)
    for j in range(n):
        data_dir = {}
        for i in range(start+1, stop+1):
            print(f"Growing 1 to {i} worms")
            t1 = time.time_ns()
            r = requests.post(f"http://{gate_list[0][0]}:{wormport}/change_size/{i}")

            while count_segment != i:
                count_segment = 0
                live_worms = []
                for gate in gate_list:
                    r = requests.get(f"http://{gate[0]}:{gate[1]}/info")
                    response = json.loads(r.text)
                    if int(response['numsegments']) == 1:
                        count_segment += 1
                        live_worms.append(gate[0])
                    if count_segment == i:
                        break
            while leader_count < i//2:
                leader_dict = {}
                for worm in live_worms:
                    try:
                        r = requests.get(f"http://{worm}:{wormport}/benchmark_leader")
                    except requests.exceptions.ConnectionError:
                        continue
                    response = json.loads(r.text)
                    try:
                        leader_dict[response["leader"]] += 1
                    except KeyError:
                        leader_dict[response["leader"]] = 1

                for key in leader_dict:
                    if leader_dict[key] > leader_count:
                        leader_count = leader_dict[key]
            t2 = time.time_ns()
            data_dir[i] = t2-t1
            #Change size back to one
            r = requests.post(f"http://{gate_list[0][0]}:{wormport}/change_size/1")
            time.sleep(20)
        data_list.append(data_dir)
    with open('spawn_worm.data', 'w') as file: 
        for key in data_list[0]:
            data = f"{key}"
            for data_dict in data_list:
                data += f",{data_dict[key]}"
            file.write(data+"\n")

def benchmark_killed(start, stop,num_worms = 10, n=3):
    gate_list = open_gates(num_worms)
    #Upload one worm
    spawn_worm(gate_list[0])
    #Let worm have time to wake up
    time.sleep(1)
    #Spawn num_worms
    r = requests.post(f"http://{gate_list[0][0]}:{wormport}/change_size/{num_worms}")
    #Let all worms wake up
    
    count_segment = 0
    leader_count = 0
    print("Starting benvchmark")
    data_list = []
    for j in range(n):
        data_dir = {}
        for i in range(start+1, stop+1):
            time.sleep(3)
            print(f"Killing {i} worms")
            t1 = time.time_ns()
            for j in range(1,num_worms):
                r = requests.post(f"http://{gate_list[j][0]}:{gate_list[j][1]}/kill_worms")

            while count_segment != num_worms:
                count_segment = 0
                live_worms = []
                for gate in gate_list:
                    r = requests.get(f"http://{gate[0]}:{gate[1]}/info")
                    response = json.loads(r.text)
                    if int(response['numsegments']) == 1:
                        count_segment += 1
                        live_worms.append(gate[0])
                    if count_segment == i:
                        break
            while leader_count < i//2:
                leader_dict = {}
                for worm in live_worms:
                    try:
                        r = requests.get(f"http://{worm}:{wormport}/benchmark_leader")
                    except requests.exceptions.ConnectionError:
                        continue
                    response = json.loads(r.text)
                    try:
                        leader_dict[response["leader"]] += 1
                    except KeyError:
                        leader_dict[response["leader"]] = 1

                for key in leader_dict:
                    if leader_dict[key] > leader_count:
                        leader_count = leader_dict[key]
            t2 = time.time_ns()
            data_dir[i] = t2-t1
            #Change size back to one
            r = requests.post(f"http://{gate_list[0][0]}:{wormport}/change_size/1")
            time.sleep(20)
        data_list.append(data_dir)
    with open('kill_worm.data', 'w') as file: 
        for key in data_list[0]:
            data = f"{key}"
            for data_dict in data_list:
                data += f",{data_dict[key]}"
            file.write(data+"\n")

def parse_arg():
    def signal_handler(sig, frame):
        print('\nTERMENATING ALL NODES!')
        os.system(f'cat {file} | ./worm_gate/wormgates_kill.sh')
        sys.exit(0)


    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--nodes', type=int, default=20, required=True)
    parser.add_argument('-p', '--port', type=int, default=64209, required=False)

    if len(sys.argv) == 1:
        parser.print_help()
        exit()

    args = parser.parse_args()

    write_to_node_file(args.nodes, args.port)
    os.system(f'cat {file} | ./wormgates_start.sh')

    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.pause()
if __name__ == "__main__":
    # benchmark_grow(1,20,10)    
    benchmark_killed(1,9)
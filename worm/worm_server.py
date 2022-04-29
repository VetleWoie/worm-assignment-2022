from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from threading import Thread 
import requests
import json
import os
import time
import logging
logging.basicConfig(filename='/home/vho023/3203/worm/worm-assignment-2022/debug.log', level=logging.DEBUG)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        logging.debug(f"{self.server.id}: Got request: {self.path}")
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
    def do_POST(self):
        pass

class Worm_server(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass,gate_server, num_worms):

        super().__init__(server_address, RequestHandlerClass)
        self.main_thread = Thread(target=self.run)
        self.gate = gate_server
        self.id = server_address[0]
        self.worm_ports = server_address[1]
        self.gate_info = self.get_gate_info(self.gate)
        self.fellow_worms = []
        self.max_worms = num_worms
        self.leader = True

        #Last thing to do in init
        self.main_thread.start()
        self.serve_forever()
    
    def run(self):
        logging.debug(f"{self.id}: Starting body")

        while True:
            time.sleep(5)
            live_list = []
            dead_list = []
            for gate, port in self.gate_dict.items():
                is_alive = self.ping_worm((gate, port))
                self.gate_dict[gate][1] = is_alive
                if is_alive:
                    live_list.append(gate)
                else:
                    dead_list.append(gate)

            if len(live_list) < self.max_worms:
                #Need to spawn new worms
                if len(live_list)==0:
                    for gate in dead_list[:self.max_worms]:
                        self.spawn_worm((gate, self.gate_dict[gate]))
                elif len(live_list)==self.max_worms:
                    continue
                else:
                    self.elect_leader()
                    if self.leader:
                        for gate in dead_list[:self.max_worms-len(live_list)]:
                            self.spawn_worm((gate, self.gate_dict[gate]))

    def elect_leader(self):
        pass

    def get_gate_info(self, gate):
        r = requests.get(f"http://{gate[0]}:{gate[1]}/info")
        info = json.loads(r.text)
        self.gate_dict = {}
        for i, gate in enumerate(info["other_gates"]):
            gate = gate.split(":")
            self.gate_dict[gate[0]] = int(gate[1])
            info["other_gates"][i] = (gate[0], int(gate[1]))

        return info
    
    def ping_worm(self, gate):
        logging.debug(f"{self.id}: Pinging worm on gate {gate[0]} ")
        try:
            r = requests.get(f"http://{gate[0]}:{self.worm_ports}/ping")
        except requests.exceptions.ConnectionError:
            logging.debug(f"{self.id}: Can't reach worm on gate {gate[0]} ")
            return False
        if r.status_code == 200:
            logging.debug(f"{self.id}: Worm on gate {gate[0]} is open")
            return True

    
    def spawn_worm(self, gate):
        logging.debug(f"{self.id}: Spawning new worm at {gate}")
        executable_path = os.path.dirname(os.path.realpath(__file__))
        with open(executable_path,"rb") as exe:
            executable = exe.read()
        # url = "http://{gate[0]}:{gate[1]}/worm_entrance?args={gate[0]}:{gate[1]}&args={self.max_worms}"
        # logging.debug(f"{self.id}: Spawning new worm at {gate} with {url}")
        r = requests.post(f"http://{gate[0]}:{gate[1]}/worm_entrance?args={gate[0]}:{gate[1]}&args={self.max_worms}", data=executable)
        self.fellow_worms.append(gate)

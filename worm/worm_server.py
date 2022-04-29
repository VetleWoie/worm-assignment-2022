from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from threading import Thread, Lock
import requests
import json
import os
import time
import random
import logging

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        logging.debug(f"{self.server.id}: Got request: {self.path}")
        args = self.path.split('/')[1:]
        if args[0] == "ping":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
        elif args[0] == 'election':
            #Take voting lock
            logging.debug(f"{self.server.id}: Got election request")
            self.server.voting_booth.acquire()
            if int(args[1]) > self.server.epoch:
                if self.server.voted:
                    logging.debug(f"{self.server.id}: Allready voted")
                    self.send_response(412)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                else:
                    logging.debug(f"{self.server.id}: Vote for new leader")
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.server.voted = True
            else: # epoch <= self.epoch
                logging.debug(f"{self.server.id}: Epoch too small")
                self.send_response(498)
                self.send_header("Content-type", "text/json")
                self.end_headers()
                response = {'epoch' : self.server.epoch, 'leader' : self.server.leader}
                self.wfile.write(json.dumps(response).encode())
            #Release voting lock
            self.server.voting_booth.release()
        elif args[0] == 'new_leader':
            epoch = int(args[1])
            new_leader = args[2]
            if epoch <= self.server.epoch:
                logging.debug(f"{self.server.id}: Epoch too small on leader broadcast")
                self.send_response(498)
                self.send_header("Content-type", "text/json")
                self.end_headers()
                response = {'epoch' : self.server.epoch, 'leader' : self.server.leader}
                self.wfile.write(json.dumps(response).encode())
            else:
                logging.debug(f"{self.server.id}: Got new leader broadcast, setting leader to {new_leader} at epoch {epoch}")
                self.send_response(200)
                self.send_header("Content-type", "text/json")
                self.end_headers()
                self.server.leader = new_leader
                self.server.epoch = epoch
                self.server.voted = False
        else:
            logging.debug(f"{self.server.id}: Got wrong request: Request: {self.path}")
            self.send_response(498)
            self.send_header("Content-type", "text/json")
            self.end_headers()

    def do_POST(self):
        pass

        

class Worm_server(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass,gate_server, num_worms):

        logging.basicConfig(filename=f'/home/vho023/3203/worm/worm-assignment-2022/debug_{server_address[0]}.log', level=logging.DEBUG)
        super().__init__(server_address, RequestHandlerClass)
        self.main_thread = Thread(target=self.run)
        self.gate = gate_server
        self.id = server_address[0]
        self.worm_ports = server_address[1]
        self.gate_info = self.get_gate_info(self.gate)
        self.fellow_worms = []
        self.max_worms = num_worms-1
        self.epoch = 0
        self.voted = False
        self.leader = None
        self.voting_booth = Lock()

        #Last thing to do in init
        self.main_thread.start()
        self.serve_forever()
    
    def run(self):
        logging.debug(f"{self.id}: Starting body")
        live_list,dead_list = self.get_worm_state()
        self.elect_leader(live_list)
        while True:
            time.sleep((random.random()*5)+1)

            if self.leader == self.id:
                live_list,dead_list = self.get_worm_state()
                logging.debug(f"{self.id}: Found {len(live_list)} live worms")
                if len(live_list) <= self.max_worms:
                    logging.debug(f"{self.id}: Should be {self.max_worms} worms, Need to spawn {self.max_worms-len(live_list)}")
                    for gate in dead_list[:self.max_worms-len(live_list)]:
                                self.spawn_worm((gate, self.gate_dict[gate]))
            else:
                #Ping leader
                is_alive = self.ping_worm((self.leader, self.worm_ports))
                if not is_alive:
                    #Leader has fallen, elect new leader
                    logging.debug(f"{self.id}: Leader has fallen, elect new leader")
                    live_list, _ = self.get_worm_state()
                    self.elect_leader(live_list)

    def get_worm_state(self):
        live_list = []
        dead_list = []
        for gate, port in self.gate_dict.items():
                        is_alive = self.ping_worm((gate, port))
                        if is_alive:
                            live_list.append(gate)
                        else:
                            dead_list.append(gate)
        return live_list, dead_list

    def elect_leader(self, live_list):
        logging.debug(f"{self.id}: Throwing election")
        self.epoch += 1
        if len(live_list) == 0:
            logging.debug(f"{self.id}: All alone, leader by deafault")
            self.leader = self.id
            return
        vote_count = 0
        for gate in live_list:
            r = requests.get(f"http://{gate}:{self.worm_ports}/election/{self.epoch}")
            logging.debug(f"{self.id}: Got response: {r.status_code}")
            if r.status_code == 200:
                logging.debug(f"{self.id}: Got vote")
                vote_count += 1
            elif r.status_code == 498:
                response = json.loads(r.text)
                self.leader = response['leader']
                self.epoch = response['epoch']
                logging.debug(f"{self.id}: Epoch too small, got new leader {self.leader}, and new epoch {self.epoch}")
                return
        if vote_count > len(live_list)//2:
            logging.debug(f"{self.id}: Won election")
            self.leader = self.id
            #Broadcast new leader
            for gate in live_list:
                try:
                    logging.debug(f"{self.id}: Broadcasting my victory  to {gate}")
                    r = requests.get(f"http://{gate}:{self.worm_ports}/new_leader/{self.epoch}/{self.id}")
                except requests.exceptions.ConnectionError:
                    logging.debug(f"{self.id}: Could not broadcast leader to {gate}")
                    continue
            if r.status_code == 200:
                return
            elif r.status_code == 498:
                logging.debug(f"{self.id}: Epoch too small")
                response = json.loads(r.text.decode())
                self.leader = response['leader']
                self.epoch = response['epoch']
                return

        else:
            logging.debug(f"{self.id}: Lost election")

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
        r = requests.post(f"http://{gate[0]}:{gate[1]}/worm_entrance?args={gate[0]}:{gate[1]}&args={self.max_worms+1}", data=executable)
        self.fellow_worms.append(gate)

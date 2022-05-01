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
        logging.debug(f"{self.server.id}: Got GET request: {self.path}")
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
        # logging.debug(f"{self.server.id}: Got POST request: {self.path}")
        args = self.path.split('/')[1:]
        logging.debug(f"{self.server.id}: Got POST request: args: {args}")
        if args[0] == "shutdown":
            logging.debug(f"{self.server.id}: Got shutdown request")
            self.send_response(200)
            self.send_header("Content-type", "text/json")
            self.end_headers()
            self.server.shutdown()
        elif args[0] == "kill_all":
            logging.debug(f"{self.server.id}: Got order 66 request")
            self.send_response(200)
            self.send_header("Content-type", "text/json")
            self.end_headers()
            self.server.kill_all()
        elif args[0] == "change_size":
            new_size = int(args[1])
            logging.debug(f"{self.server.id}: Got change size request, new size: {new_size}")
            self.send_response(200)
            self.send_header("Content-type", "text/json")
            self.end_headers()
            # self.server.size_lock.aquire()
            # self.server.new_size = int(new_size)
            # self.server.size_lock.release()
            self.server.change_size(new_size)
        elif args[0] == "new_size":
            new_size = int(args[1])
            logging.debug(f"{self.server.id}: Got new size from leader, new size: {new_size}")
            self.server.max_worms = new_size-1
            self.send_response(200)
            self.send_header("Content-type", "text/json")
            self.end_headers()
            logging.debug(f"{self.server.id}: Commited new size to {self.server.max_worms}")

class Worm_server(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass,gate_server, num_worms, log=False):

        if log:
            logging.basicConfig(filename=f'/home/vho023/3203/worm/worm-assignment-2022/debug_{server_address[0]}.log', level=logging.DEBUG)
        else:
            logging.disable()
        super().__init__(server_address, RequestHandlerClass)
        self.main_thread = Thread(target=self.run)
        self.gate = gate_server
        self.id = server_address[0]
        self.worm_ports = server_address[1]
        self.gate_info = self.get_gate_info(self.gate)
        self.fellow_worms = []
        self.max_worms = num_worms-1
        self.new_size = self.max_worms
        self.epoch = 0
        self.voted = False
        self.leader = None
        self.voting_booth = Lock()
        self.size_lock = Lock()
        self.alive = True

        #Last thing to do in init
        self.main_thread.start()
        self.serve_forever()
    
    def shutdown(self) -> None:
        logging.debug(f"{self.id}: Shutting down")
        super().shutdown()
        self.alive = False

    def run(self):
        logging.debug(f"{self.id}: Starting body")
        live_list,dead_list = self.get_worm_state()
        self.elect_leader(live_list)
        while self.alive:
            time.sleep((random.random()*5)+1)

            if self.leader == self.id:
                live_list,dead_list = self.get_worm_state()
                logging.debug(f"{self.id}: Found {len(live_list)} live worms")
                if len(live_list) <= self.max_worms:
                    logging.debug(f"{self.id}: Should be {self.max_worms} worms, Need to spawn {self.max_worms-len(live_list)}")
                    for gate in dead_list[:self.max_worms-len(live_list)]:
                        self.spawn_worm((gate, self.gate_dict[gate]))
                if len(live_list) > self.max_worms:
                    logging.debug(f"{self.id}: Should be {self.max_worms} worms, Need to kill {len(live_list)-self.max_worms}")
                    for gate in live_list[:len(live_list)-self.max_worms]:
                        self.kill_worm((gate, self.gate_dict[gate]))
            else:
                #Ping leader
                is_alive = self.ping_worm((self.leader, self.worm_ports))
                if not is_alive:
                    #Leader has fallen, elect new leader
                    logging.debug(f"{self.id}: Leader has fallen, elect new leader")
                    live_list, _ = self.get_worm_state()
                    self.elect_leader(live_list)
    
    def kill_all(self):
        if self.leader == self.id:
            logging.debug(f"{self.id}: Got order 66 as leader")
            live_list, _ = self.get_worm_state()
            for gate in live_list:
                logging.debug(f"{self.id}: Telling {gate} to kill self")
                r = requests.post(f"http://{gate}:{self.worm_ports}/shutdown")
            logging.debug(f"{self.id}: Everybody is dead, killing myself")
            self.shutdown()
            
        else:
            #I am follower, need to notify the leader
            logging.debug(f"{self.id}: Notify my leader {self.leader} of order 66")
            try:
                r = requests.post(f"http://{self.leader}:{self.worm_ports}/kill_all")
            except requests.exceptions.ConnectionError:
                return

    
    def change_size(self, new_size):
        if self.leader == self.id:
            live_list, _ = self.get_worm_state()
            if len(live_list) == 0:
                logging.debug(f"{self.id}: Changing size, all alone, majority by default")
                self.max_worms = new_size - 1
                return
            count = 0
            logging.debug(f"{self.id}:Need to notify followers of size change,  Found live worms {live_list}")
            for gate in live_list:
                logging.debug(f"{self.id}: Telling {gate} to change size to {new_size}")
                r = requests.post(f"http://{gate}:{self.worm_ports}/new_size/{new_size}")
                logging.debug(f"{self.id}: Got response {r.status_code} from {gate} about size change")
                if r.status_code == 200:
                    logging.debug(f"{self.id}: {gate} accepted size change to {new_size}")
                    count += 1
            #Commit if majority has accepted new size
            if count > len(live_list)//2:
                logging.debug(f"{self.id}: Got majority for size change, commiting size change")
                self.max_worms = new_size-1
        else:
            #I am follower, need to notify the leader
            logging.debug(f"{self.id}: Notify my leader {self.leader} to change size to {new_size}")
            try:
                r = requests.post(f"http://{self.leader}:{self.worm_ports}/change_size/{new_size}")
            except requests.exceptions.ConnectionError:
                return

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
        #Might need to check size
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
    
    def kill_worm(self, gate):
        logging.debug(f"{self.id}: Killing worm at {gate[0]}")
        try:
            r = requests.post(f"http://{gate[0]}:{self.worm_ports}/shutdown")
        except requests.exceptions.ConnectionError:
            #If worm allready dead, don't care
            return
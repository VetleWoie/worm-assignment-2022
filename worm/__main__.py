# import subprocess
# subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
from worm_server import Worm_server, Handler
import sys

WORMPORT = 64210


if __name__ == '__main__':
    if len(sys.argv)<3:
        print(f"Usage {sys.argv[0]} [gate:port] [NumWorms]")
        exit()
    adress = sys.argv[1].split(':')
    adress[1] = int(adress[1])
    Worm_server((adress[0], WORMPORT),Handler, adress, 0)
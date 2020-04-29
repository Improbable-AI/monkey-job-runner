
import json
import time
import random
import string
import datetime
import threading
import requests

import logging 
logger = logging.getLogger(__name__)

HEARTBEAT_TIME = 30
HEARTBEAT_FAILURE_TOLERANCE = 3


from threading import Thread
from concurrent.futures import Future


# Creates backgound decorators @threaded.  To block and get the result, use .result()
def call_with_future(fn, future, args, kwargs):
    try:
        result = fn(*args, **kwargs)
        future.set_result(result)
    except Exception as exc:
        future.set_exception(exc)

def threaded(fn):
    def wrapper(*args, **kwargs):
        future = Future()
        Thread(target=call_with_future, args=(fn, future, args, kwargs)).start()
        return future
    return wrapper


class MonkeyInstance():

    name = None
    machine_zone = None
    machine_project = None
    creation_time = None
    destruction_time = None
    ip_address = None
    state = None

    def __init__(self, name, machine_zone, machine_project, ip_address):
        super().__init__()
        self.name = name
        self.machine_zone = machine_zone
        self.machine_project = machine_project
        self.ip_address = ip_address

        threading.Thread(target=self.heartbeat_loop, daemon=True)

    def heartbeat_loop(self):
        while True:
            time.sleep(HEARTBEAT_TIME)
            r = requests.get("http://{}:9991/ping".format(self.ip_address))



    def destroy_instance(self):
        raise NotImplementedError("This is not implemented yet")

    def stop_instance(self):
        raise NotImplementedError("This is not implemented yet")
    


class MonkeyInstanceGCP(MonkeyInstance):

    ansible_info = None

    def __str__(self):
        return """Monkey GCP Instance
machine_name: {}, ip: {}, state: {}
        """.format(self.ip_address, self.machine_name, self.state)

    def get_json(self):
        return {
            "name": self.name,
            "ip_address": self.ip_address,
            "state": self.state, 
            "machine_zone": self.machine_zone, 
            "machine_project": self.machine_project, 
        }

    # Passes compute_api in order to restart instances
    def __init__(self, ansible_info):
        name = ansible_info["name"]
        machine_zone = ansible_info["zone"]
        machine_project = ansible_info["project"]
        # Look for public IP
        network_interfaces = ansible_info.get("networkInterfaces", [])
        access_configs = next(iter(network_interfaces), dict()).get("accessConfigs", [])
        self.ip_address = next(iter(access_configs), dict()).get("natIP", None)

        super().__init__(name=name, machine_zone=machine_zone, machine_project=machine_project, ip_address=self.ip_address)
        self.ansible_info = ansible_info
        self.state = ansible_info["status"]


    





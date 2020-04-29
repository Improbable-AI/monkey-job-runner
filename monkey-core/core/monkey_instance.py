
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

    machine_name = None
    machine_zone = None
    machine_project = None
    creation_time = None
    destruction_time = None
    ip_address = None

    def __init__(self, machine_name, machine_zone, machine_project, ip_address):
        super().__init__()
        self.machine_name = machine_name
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

    compute_api = None

    def __str__(self):
        return """Monkey GCP Instance
ip: {}
machine_name: {}
        """.format(self.ip_address, self.machine_name)

    # Passes compute_api in order to restart instances
    def __init__(self, compute_api=None,  machine_name=None, machine_zone=None, machine_project=None, ip_address=None):
        super().__init__(machine_name=machine_name, machine_zone=machine_zone, machine_project=machine_project, ip_address=ip_address)
        self.compute_api = compute_api

    @classmethod
    @threaded
    def from_creation_operation(cls, compute_api=None, machine_name=None, machine_zone=None, machine_project=None, operation_name=None):
        assert compute_api is not None, "Compute API missing"
        assert operation_name is not None, "Operation Name missing"
        MonkeyInstanceGCP.wait_for_operation(compute_api=compute_api, machine_project=machine_project, machine_zone=machine_zone, operation_name=operation_name, silent=False)
        ip_address = MonkeyInstanceGCP.get_ip_address(compute_api=compute_api, machine_name=machine_name, machine_zone=machine_zone, machine_project=machine_project)
        assert ip_address is not None, "Was not able to get a public ip address"
        return cls(compute_api=compute_api, machine_name=machine_name, machine_zone=machine_zone, machine_project=machine_project, ip_address=ip_address)
    
    @classmethod
    def wait_for_operation(cls, compute_api=None, machine_project=None, machine_zone=None, operation_name=None, timeout=40, silent=True):
        assert compute_api is not None, "Compute API missing"
        assert operation_name is not None, "Operation Name missing"
        if not silent:
            logger.info('Waiting for operation to finish...')
        
        start = time.time()
        while time.time() - start < timeout:
            result = compute_api.zoneOperations().get(
                project=machine_project,
                zone=machine_zone,
                operation=operation_name).execute()
            if not silent:
                logger.debug(result)
            if result['status'] == 'DONE':
                if not silent:
                    logger.info("Operation {} done.".format(operation_name))
                if 'error' in result:
                    raise Exception(result['error'])
                return result
            time.sleep(2)

        raise TimeoutError("Waited for the operation to complete more than maximum timeout: {}".format(timeout))
    
    @classmethod
    def get_ip_address(cls,compute_api=None, machine_name=None, machine_zone=None, machine_project=None):
        assert compute_api is not None
        print("Getting IP Address")
        result = compute_api.instances().get(
            project=machine_project,
            zone=machine_zone,
            instance=machine_name
        ).execute()
        print(result)
        network_interfaces = result.get("networkInterfaces",[])
        assert len(network_interfaces) > 0, "No Network Interfaces found"
        access_configs = network_interfaces[0].get("accessConfigs", [])
        assert len(access_configs) > 0, "Access configs not found"
        public_ip = access_configs[0].get("natIP", None)
        return public_ip


    @classmethod
    def from_ip_address(cls, ip_address=None, timeout=200):
        if ip_address is None:
            return None
        print("Instantiating with ip: {}".format(ip_address))
        start = time.time()
        print(start)
        print("Elapsed", (time.time() - start))
        print(timeout)
        while (time.time() - start) < timeout:
            r = requests.get("http://{}:9991/info".format(ip_address))
            if r.status_code == 200:
                response_json = r.json()
                print(response_json)
                try:
                    machine_name = response_json['machine_name']
                    machine_zone = response_json['machine_zone']
                    machine_project = response_json['machine_project']
                    return cls(machine_name=machine_name, machine_zone=machine_zone, machine_project=machine_project, ip_address=ip_address)
                except Exception as e:
                    print("Failed to parse expected info from {}:\n{}"\
                        .format(ip_address, json.dumps(response_json, indent=2)))

            else:
                print("Failed to get response from {}".format(ip_address))
            time.sleep(5)

        return None

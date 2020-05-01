
import json
import time
import random
import string
import datetime
import threading
import requests
import yaml
import os
import logging 
logger = logging.getLogger(__name__)

HEARTBEAT_TIME = 30
HEARTBEAT_FAILURE_TOLERANCE = 3


from threading import Thread
from concurrent.futures import Future
import ansible_runner


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


    def install_dependency(self, dependency):
        raise NotImplementedError("This is not implemented yet")

    def setup_job(self, job, credential_file=None):
        raise NotImplementedError("This is not implemented yet")


    def destroy_instance(self):
        raise NotImplementedError("This is not implemented yet")

    def stop_instance(self):
        raise NotImplementedError("This is not implemented yet")
    


class MonkeyInstanceGCP(MonkeyInstance):

    ansible_info = None

    def __str__(self):
        return """Monkey GCP Instance
name: {}, ip: {}, state: {}
        """.format(self.ip_address, self.name, self.state)

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
        print(ansible_info)
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


    def install_dependency(self, dependency):
        print("Instance installing: ", dependency)
        runner = ansible_runner.run(host_pattern=self.name, private_data_dir="ansible", module="include_role", module_args="name=install/{}".format(dependency))
        print(runner.stats)
        if len(runner.stats.get("failures")) != 0:
            return False
        return True

    def get_home_directory_from_service_key(self, service_key_file):
        with open(service_key_file, 'r') as service_file:
            service_account = yaml.load(service_file, Loader=yaml.FullLoader)
            home = "/home/sa_" +service_account["client_id"]
            return home
        return "~/"

    def setup_data_item(self, data_item, provider_info):
        credential_file = provider_info.get("gcp_cred_file", None)
        print(data_item)
        print(provider_info)
        monkeyfs_path = provider_info.get("monkeyfs_path", "/monkeyfs")
        home_dir_path = self.get_home_directory_from_service_key(credential_file)
        print("joining", monkeyfs_path, "data")
        source_file = os.path.join(monkeyfs_path, "data")
        data_name = data_item["name"]
        data_path = data_item["path"]
        data_checksum = data_item["dataset_checksum"]
        dataset_filename = data_item["dataset_filename"]
        installation_location = os.path.join(home_dir_path, data_item["path"])
        dataset_full_path = os.path.join(monkeyfs_path, "data", data_name, data_checksum, dataset_filename)
        print("Copying dataset from", dataset_full_path, " to ", installation_location)

        runner = ansible_runner.run(host_pattern=self.name, private_data_dir="ansible", 
                                    module="file", 
                                    module_args="path={} state=directory"
                                    .format(installation_location))

        runner = ansible_runner.run(host_pattern=self.name, private_data_dir="ansible", 
                                    module="unarchive", 
                                    module_args="src={} remote_src=True dest={} creates=yes"
                                    .format(dataset_full_path, installation_location))
        print(runner.stats)
        if len(runner.stats.get("failures")) != 0:
            return False, "Failed to extract archive"

        return True, "Successfully setup data item"

    def setup_job(self, job, provider_info=dict()):
        print("Setting up job: ", job)

        credential_file = provider_info.get("gcp_cred_file", None)
        print("Credential file", credential_file)
        gcp_storage_name = provider_info.get("gcp_storage_name", "monkeyfs")
        monkeyfs_path = provider_info.get("monkeyfs_path", "/monkeyfs")
        if credential_file is None:
            return False, "Service account credential file is not provided"

        print("Mounting filesystem...")
        runner = ansible_runner.run(host_pattern=self.name, private_data_dir="ansible", module="include_role", module_args="name=gcp/mount_fs", 
                                    extravars={
                                        "gcp_cred_file":credential_file,
                                        "gcp_storage_name": gcp_storage_name,
                                        "monkeyfs_path": monkeyfs_path
                                        })
        print(runner.stats)
        if len(runner.stats.get("failures")) != 0:
            return False, "Failed to mount filesystem"

        for data_item in job.get("data", []):
            print("Setting up data item", data_item)
            success, msg = self.setup_data_item(data_item=data_item, provider_info=provider_info)
            if success == False:
                return success, msg

        return True, "Setup job correctly"
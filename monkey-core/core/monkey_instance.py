
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

    def setup_job(self, job, provider_info=dict()):
        raise NotImplementedError("This is not implemented yet")

    def run_job(self, job, provider_info=dict()):
        raise NotImplementedError("This is not implemented yet")

    def cleanup_job(self, job, provider_info=dict()):
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

        if len(runner.stats.get("failures")) != 0:
            return False
        return True

    def get_home_directory_from_service_key(self, service_key_file):
        with open(service_key_file, 'r') as service_file:
            service_account = yaml.load(service_file, Loader=yaml.FullLoader)
            home = "/home/sa_" +service_account["client_id"]
            return home
        return "~/"

    def setup_data_item(self, data_item, monkeyfs_path, home_dir_path):
        

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

    def unpack_code_and_persist(self, job_uid, monkeyfs_path, home_dir_path):
        job_path = os.path.join(monkeyfs_path, "jobs", job_uid)

        runner = ansible_runner.run(host_pattern=self.name, private_data_dir="ansible", 
                            module="copy", 
                            module_args="src={} dest={} remote_src=true"
                            .format(job_path + "/", home_dir_path))
        if len(runner.stats.get("failures")) != 0:
              return False, "Failed to copy directory"
        
        runner = ansible_runner.run(host_pattern=self.name, private_data_dir="ansible", 
                                    module="unarchive", 
                                    module_args="src={} remote_src=True dest={} creates=yes"
                                    .format(os.path.join(job_path, "code.tar"), home_dir_path))
        if len(runner.stats.get("failures")) != 0:
              return False, "Failed to extract archive"

        return True, "Unpacked code and persisted directories successfully"
    
    def setup_persist_folder(self, job_uid, monkeyfs_bucket_name, home_dir_path, persist):
        print("Persisting folder: ", persist)
        persist_path = persist["path"]
        persist_name = "." + persist_path.replace("/", "_") + "_sync.sh"
        script_path = os.path.join(home_dir_path, persist_name)
        monkeyfs_output_folder = "gs://" + os.path.join(monkeyfs_bucket_name, "jobs", job_uid, persist_path)
        persist_folder_path = os.path.join(home_dir_path, persist_path)

        print("Output folder: ", monkeyfs_output_folder)
        print("Input folder: ", persist_folder_path)
        runner = ansible_runner.run(host_pattern=self.name, private_data_dir="ansible", module="include_role", module_args="name=configure/persist_folder", 
                                    extravars={
                                        "persist_folder_path": persist_folder_path,
                                        "persist_script_path": script_path,
                                        "bucket_path": monkeyfs_output_folder,
                                        })
                            
        if len(runner.stats.get("failures")) != 0:
              return False, "Failed to create persisted directory: "+ persist_path
        return True, "Setup persist ran successfully"
    
    def setup_logs_folder(self, job_uid, monkeyfs_bucket_name, home_dir_path):
        print("Persisting logs: ")
        logs_path = os.path.join(home_dir_path, "logs")
        monkeyfs_output_folder = "gs://" + os.path.join(monkeyfs_bucket_name, "jobs", job_uid, "logs")
        script_path = os.path.join(home_dir_path, ".logs_sync.sh")
        runner = ansible_runner.run(host_pattern=self.name, private_data_dir="ansible", module="include_role", module_args="name=configure/persist_folder", 
                                    extravars={
                                        "persist_folder_path": logs_path,
                                        "persist_script_path": script_path,
                                        "bucket_path": monkeyfs_output_folder,
                                        "persist_time": 3,
                                        })
                            
        if len(runner.stats.get("failures")) != 0:
              return False, "Failed to create persisted logs folder"
        return True, "Setup logs persistence ran successfully"


    def setup_job(self, job, provider_info=dict()):
        print("Setting up job: ", job)
        job_uid = job["job_uid"]
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

        home_dir_path = self.get_home_directory_from_service_key(credential_file)

        for data_item in job.get("data", []):
            print("Setting up data item", data_item)
            success, msg = self.setup_data_item(data_item=data_item, monkeyfs_path=monkeyfs_path, home_dir_path=home_dir_path)
            if success == False:
                return success, msg
        
        success, msg = self.unpack_code_and_persist(job_uid=job_uid, monkeyfs_path=monkeyfs_path, home_dir_path=home_dir_path)
        if success == False:
            return success, msg
        print("Success in unpacking all datasets")

        print("Setting up logs folder")
        success, msg = self.setup_logs_folder(job_uid=job_uid, monkeyfs_bucket_name=gcp_storage_name, home_dir_path=home_dir_path)
        if success == False:
            return success, msg

        for persist_item in job.get("persist", []):
            print("Setting up persist item", persist_item)
            success, msg = self.setup_persist_folder(job_uid=job_uid, monkeyfs_bucket_name=gcp_storage_name, home_dir_path=home_dir_path, persist=persist_item)
            if success == False:
                return success, msg

        return True, "Successfully setup the job"

    def setup_dependency_manager(self, run_yml):
        env_type = run_yml["env_type"]
        env_file = run_yml["env_file"]
        print("Env type: ", env_type)
        print("Env file: ", env_file)

        if env_type == "conda":
            runner = ansible_runner.run(host_pattern=self.name, private_data_dir="ansible", 
                                        module="include_role", module_args="name=run/setup_conda", 
                                        extravars={
                                        "environment_file": env_file,
                                        })
        elif env_file == "pip":
            return False, "pip environment manager not implemented yet"
        else:
            return False, "Provided or missing dependency manager"

        if len(runner.stats.get("failures")) != 0:
              return False, "Failed to initialize environment manager"

        return True, "Successfully created dependency manager and stored initialization in .profile"

    def execute_command(self, cmd,  run_yml):
        print("Executing cmd: ", cmd)
        print("Environment Variables:", run_yml.get("env", dict()))
        final_command = ". ~/.profile; " + cmd +  " 2>&1 | tee logs/run.log"
        runner = ansible_runner.run(host_pattern=self.name, private_data_dir="ansible", 
                                    module="include_role", module_args="name=run/cmd", 
                                    extravars={
                                        "run_command": cmd
                                    },
                                    envvars=run_yml.get("env", dict()))

        if len(runner.stats.get("failures")) != 0:
              return False, "Failed to run command properly: " + cmd
        
        return True, "Successfully ran job"

    def run_job(self, job, provider_info=dict()):
        print("Running job: ", job)
        job_uid = job["job_uid"]
        credential_file = provider_info.get("gcp_cred_file", None)
        gcp_storage_name = provider_info.get("gcp_storage_name", "monkeyfs")
        monkeyfs_path = provider_info.get("monkeyfs_path", "/monkeyfs")
        if credential_file is None:
            return False, "Service account credential file is not provided"

        print("Setting up dependency manager...")
        success, msg = self.setup_dependency_manager(job["run"])
        if success == False:
            return success, msg

        success, msg = self.execute_command(cmd=job["cmd"], run_yml=job["run"])
        if success == False:
            return success, msg

        print("\n\nRan job:", job_uid, " SUCCESSFULLY!\n\n")

        return True, "Job completed"

    def cleanup_job(self, job, provider_info=dict()):
        job_uid = job["job_uid"]
        print("\n\nTerminating Machine:", job_uid, "\n\n")

        delete_instance_params = {
            "monkey_job_uid": job_uid,
            "zone": provider_info["zone"],
            "gcp_project": provider_info["project"],
            "gcp_cred_kind" : "serviceaccount",
            "gcp_cred_file":provider_info["gcp_cred_file"],

        }

        print(provider_info)

        runner = ansible_runner.run(host_pattern="localhost", private_data_dir="ansible", 
                                    module="include_role", module_args="name=gcp/delete", 
                                    extravars=delete_instance_params)
        
        print(runner.stats)
        if len(runner.stats.get("failures")) != 0:
            print("Failed Deletion of machine")
            return False, "Failed to cleanup job after completion"
        return True, "Succesfully cleaned up job"
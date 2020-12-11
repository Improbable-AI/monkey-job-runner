import datetime
import functools
import json
import logging
import os
import threading

import ansible_runner
import monkey_global
import requests
import yaml
from setup_scripts.utils import (aws_cred_file_environment, get_aws_vars,
                                 printout_ansible_events)

from core.monkey_instance import MonkeyInstance

logger = logging.getLogger(__name__)


class MonkeyInstanceLocal(MonkeyInstance):
    ansible_info = None

    def __str__(self):
        return """Monkey Local Instance
name: {}, ip: {}, state: {}
        """.format(self.ip_address, self.name, self.state)

    def get_json(self):
        return {
            "name": self.name,
            "ip_address": self.ip_address,
            "state": self.state,
        }

    # Passes compute_api in order to restart instances
    def __init__(self, provider, name, hostname):
        print("Creating local instance")
        super().__init__(name=name, ip_address=hostname)
        self.provider = provider
        self.state = "unknown"

        try:
            with open("local.yml", 'r') as local_yaml_file:
                local_yaml = yaml.full_load(local_yaml_file)
                hosts = local_yaml.get("hosts", [])
                extra_vars = None
                for h in hosts:
                    if h[0] == self.name:
                        extra_vars = h[1]
                if extra_vars is not None:
                    print("Additional local vars detected: ", extra_vars)
                    self.additional_extravars.update(extra_vars)
        except Exception as e:
            print(e)

        passes_setup = self.check_setup()
        if passes_setup:
            print(f"Instance {self.name} successfully created and configured")
        else:
            raise Exception("Failed to create instance")

        self.offline_count = 0

    def update_instance_details(self, other):
        super().update_instance_details(other)
        self.ansible_info = other.ansible_info
        self.state = other.state

    def check_setup(self):
        print(f"Checking setup of instance: {self.name}")

        uuid = self.update_uuid()
        runner = self.run_ansible_role(
            rolename="local/setup/machine",
            extravars=self.provider.get_local_vars(),
            uuid=uuid)
        print(runner.status)
        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Failed to setup machine")
            return False

        return True

    def check_online(self):

        try:
            r = requests.get("http://{}:9991/ping".format(self.ip_address),
                             timeout=4)
        except:
            self.offline_count += 1
            return self.offline_count >= self.offline_retries
        if not r.ok:
            self.offline_count += 1
        if self.offline_count >= self.offline_retries:
            return False
        self.offline_count = 0
        return True

    def install_dependency(self, dependency):
        print("Instance Dependency Installation SKIPPED (local): ", dependency)
        return True

    def get_scratch_dir(self):
        local_vars = self.provider.get_local_vars()
        monkey_scratch = local_vars.get("monkey_scratch")
        return monkey_scratch

    def get_monkeyfs_dir(self):
        local_vars = self.provider.get_local_vars()
        monkeyfs_path = local_vars.get("monkeyfs_path")
        return monkeyfs_path

    def setup_data_item(self, data_item, job_uid):
        data_name = data_item["name"]
        data_checksum = data_item["dataset_checksum"]
        dataset_filename = data_item["dataset_filename"]

        installation_location = os.path.join(get_scratch_dir(), job_uid,
                                             data_item["path"])
        dataset_full_path = os.path.join(monkeyfs_path, "data", data_name,
                                         data_checksum, dataset_filename)
        print("Copying dataset from", dataset_full_path, " to ",
              installation_location)

        uuid = self.update_uuid()

        runner = self.run_ansible_module(modulename="file",
                                         args={
                                             "path": installation_location,
                                             "state": "directory"
                                         },
                                         uuid=uuid)

        runner = self.run_ansible_module(modulename="unarchive",
                                         args={
                                             "src": dataset_full_path,
                                             "remote_src": "True",
                                             "dest": installation_location,
                                             "creates": "yes",
                                         },
                                         uuid=uuid)

        print(runner.stats)
        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Failed to setup data item")
            return False, "Failed to extract archive"

        print("Successfully setup data item")
        return True, "Successfully setup data item"

    def unpack_job_dir(self, job_uid, monkeyfs_path, home_dir_path):
        job_path = os.path.join(monkeyfs_path, "jobs", job_uid)

        uuid = self.update_uuid()
        runner = self.run_ansible_module(
            modulename="copy",
            args=f"src={job_path + '/' } dest={home_dir_path} remote_src=true",
            uuid=uuid)
        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Failed to copy directory")
            return False, "Failed to copy directory"

        print("Unpacked code and persisted directory successfully")
        return True, "Unpacked code and persisted directories successfully"

    def unpack_code_and_persist(self, code_item, monkeyfs_path, home_dir_path):
        print(code_item)
        run_name = code_item["run_name"]
        checksum = code_item["codebase_checksum"]
        extension = code_item["codebase_extension"]
        code_tar_path = os.path.join(monkeyfs_path, "code", run_name, checksum,
                                     "code" + extension)

        uuid = self.update_uuid()
        print("Code tar path: ", code_tar_path)
        print("Home dir: ", home_dir_path)
        runner = self.run_ansible_module(modulename="unarchive",
                                         args={
                                             "src": code_tar_path,
                                             "remote_src": "True",
                                             "dest": home_dir_path,
                                             "creates": "yes"
                                         },
                                         uuid=uuid)
        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Unpacked code and persisted directory successfully")
            return False, "Failed to extract archive"

        print("Unpacked code and persisted directory successfully")
        return True, "Unpacked code and persisted directories successfully"

    def setup_persist_folder(self, job_uid, home_dir_path, persist):
        print("Persisting folder: ", persist)
        persist_path = persist
        persist_name = persist.replace("/", "_") + "_sync.sh"
        script_path = os.path.join(home_dir_path, "sync", persist_name)
        monkeyfs_output_folder = \
            os.path.join("/monkeyfs", "jobs", job_uid, persist_path, "")
        persist_folder_path = os.path.join(home_dir_path, persist_path, "")

        print("Output folder: ", monkeyfs_output_folder)
        print("Input folder: ", persist_folder_path)

        uuid = self.update_uuid()
        persist_folder_args = {
            "persist_folder_path": persist_folder_path,
            "persist_script_path": script_path,
            "bucket_path": monkeyfs_output_folder,
        }
        runner = self.run_ansible_role(rolename="aws/configure/persist_folder",
                                       extravars=persist_folder_args,
                                       uuid=uuid)

        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Failed to create persisted directory: " + persist_path)
            return False, f"Failed to create persisted directory: {persist_path}"
        return True, "Setup persist ran successfully"

    def start_persist(self, job_uid, home_dir_path, persist):
        print("Persisting folder: ", persist)
        persist_path = persist
        script_path = os.path.join(home_dir_path, "sync", "persist_all.sh")
        script_loop_path = os.path.join(home_dir_path, "sync",
                                        "persist_all_loop.sh")
        monkeyfs_output_folder = \
            os.path.join("/monkeyfs", "jobs", job_uid, persist_path, "")
        persist_folder_path = os.path.join(home_dir_path, persist_path, "")

        uuid = self.update_uuid()
        start_persist_args = {
            "persist_folder_path": persist_folder_path,
            "persist_script_path": script_path,
            "persist_loop_script_path": script_loop_path,
            "bucket_path": monkeyfs_output_folder,
        }
        runner = self.run_ansible_role(rolename="aws/configure/start_persist",
                                       extravars=start_persist_args,
                                       uuid=uuid)

        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Failed to create persisted directory: " + persist_path)
            return False, "Failed to create persisted start script: "
        return True, "Start persist ran successfully"

    def setup_logs_folder(self, job_uid, home_dir_path):
        print("Persisting logs: ")
        logs_path = os.path.join(home_dir_path, "logs", "")
        monkeyfs_output_folder = \
            os.path.join("/monkeyfs", "jobs", job_uid, "logs", "")
        script_path = os.path.join(home_dir_path, ".logs_sync.sh")
        uuid = self.update_uuid()
        persist_folder_args = {
            "persist_folder_path": logs_path,
            "persist_script_path": script_path,
            "bucket_path": monkeyfs_output_folder,
            "persist_time": 3,
        }
        runner = self.run_ansible_role(rolename="aws/configure/persist_folder",
                                       extravars=persist_folder_args,
                                       uuid=uuid)

        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Failed to create persisted logs folder")
            return False, "Failed to create persisted logs folder"

        return True, "Setup logs persistence ran successfully"

    def setup_job(self, job, provider_info=dict()):
        print("Setting up job: ", job)
        job_uid = job["job_uid"]

        uuid = self.update_uuid()
        setup_job_args = {}

        for data_item in job.get("data", []):
            print("Setting up data item", data_item)
            success, msg = self.setup_data_item(data_item=data_item,
                                                job_uid=job_uid)
            if not success:
                return success, msg

        success, msg = self.unpack_job_dir(job_uid=job_uid,
                                           monkeyfs_path=monkeyfs_path,
                                           home_dir_path=home_dir_path)
        if not success:
            return success, msg

        for code_item in job.get("code", []):
            success, msg = self.unpack_code_and_persist(
                code_item=code_item,
                monkeyfs_path=monkeyfs_path,
                home_dir_path=home_dir_path)
            if not success:
                return success, msg
            print("Success in unpacking all datasets")

        print("Setting up logs folder")
        success, msg = self.setup_logs_folder(job_uid=job_uid,
                                              home_dir_path=home_dir_path)
        if not success:
            return success, msg

        for persist_item in job.get("persist", []):
            print("Setting up persist item", persist_item)
            success, msg = self.setup_persist_folder(
                job_uid=job_uid,
                home_dir_path=home_dir_path,
                persist=persist_item)
            if not success:
                return success, msg

        print("Starting Persist")
        success, msg = self.start_persist(job_uid=job_uid,
                                          home_dir_path=home_dir_path,
                                          persist=persist_item)
        if not success:
            return success, msg

        print("Setting up dependency manager...")
        success, msg = self.setup_dependency_manager(job["run"])
        if not success:
            return success, msg

        return True, "Successfully setup the job"

    def setup_dependency_manager(self, run_yml):
        env_type = run_yml["env_type"]
        env_file = run_yml["env_file"]
        print("Env type: ", env_type)
        print("Env file: ", env_file)

        uuid = self.update_uuid()
        env_args = {"environment_file": env_file}
        if env_type == "conda":
            runner = self.run_ansible_role(rolename="run/setup_conda",
                                           extravars=env_args,
                                           uuid=uuid)
        elif env_type == "pip":
            runner = self.run_ansible_role(rolename="run/setup_pip",
                                           extravars=env_args,
                                           uuid=uuid)
        elif env_type == "docker":
            runner = self.run_ansible_role(rolename="run/setup_docker",
                                           extravars=env_args,
                                           uuid=uuid)
        else:
            return False, "Provided or missing dependency manager"

        if runner.status == "failed" or self.get_uuid() != uuid:
            return False, "Failed to initialize environment manager"

        return True, "Successfully created dependency manager and stored initialization in .monkey_activate"

    def execute_command(self, cmd, run_yml):
        print("Executing cmd: ", cmd)
        print("Environment Variables:", run_yml.get("env", dict()))

        uuid = self.update_uuid()
        runner = self.run_ansible_role(rolename="run/cmd",
                                       extravars={"run_command": cmd},
                                       envvars=run_yml.get("env", dict()),
                                       uuid=uuid)

        if runner.status == "failed" or self.get_uuid() != uuid:
            return False, "Failed to run command properly: " + cmd

        return True, "Successfully ran job"

    def run_job(self, job, provider_info=dict()):
        print("Running job: ", job)
        job_uid = job["job_uid"]
        credential_file = provider_info.get("aws_cred_file", None)
        if credential_file is None:
            return False, "AWS Account Credential file is not provided"

        success, msg = self.execute_command(cmd=job["cmd"], run_yml=job["run"])
        if not success:
            return success, msg

        print("\n\nRan job:", job_uid, " SUCCESSFULLY!\n\n")

        print("\n\nForce Syncing outputs:", job_uid, " SUCCESSFULLY!\n\n")
        script_path = os.path.join("/home/ubuntu", "sync", "persist_all.sh")
        print(script_path)
        uuid = self.update_uuid()
        runner = self.run_ansible_shell(command=f"bash {script_path}",
                                        uuid=uuid)
        if runner.status == "failed" or self.get_uuid() != uuid:
            return False, "Failed to run sync command properly: "
        print("Ended syncing")

        return True, "Job completed"

    def cleanup_job(self, job, provider_info={}):
        job_uid = job["job_uid"]
        print("\n\nTerminating Machine:", job_uid, "\n\n")
        # Cleanup skipped for now
        print(provider_info)

        delete_instance_params = {
            "monkey_job_uid": job_uid,
            "aws_zone": provider_info["zone"],
            "aws_region": provider_info["zone"],
        }

        for key, val in get_aws_vars().items():
            delete_instance_params[key] = val

        runner = ansible_runner.run(
            host_pattern="localhost",
            private_data_dir="ansible",
            module="include_role",
            module_args="name=aws/delete",
            extravars=delete_instance_params,
            quiet=monkey_global.QUIET_ANSIBLE,
            cancel_callback=self.ansible_runner_uuid_cancel(
                self.update_uuid()))

        if runner.status == "failed":
            print("Failed Deletion of machine")
            return False, "Failed to cleanup job after completion"
        return True, "Succesfully cleaned up job"

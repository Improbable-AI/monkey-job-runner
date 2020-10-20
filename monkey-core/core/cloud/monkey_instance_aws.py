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
from core.monkey_instance import MonkeyInstance
from setup_scripts.utils import (aws_cred_file_environment, get_aws_vars,
                                 printout_ansible_events)

logger = logging.getLogger(__name__)


class MonkeyInstanceAWS(MonkeyInstance):
    ansible_info = None

    def __str__(self):
        return """Monkey AWS Instance
name: {}, ip: {}, state: {}
        """.format(self.ip_address, self.name, self.state)

    def get_json(self):
        return {
            "name": self.name,
            "ip_address": self.ip_address,
            "state": self.state,
            "machine_zone": self.machine_zone,
        }

    # Passes compute_api in order to restart instances
    def __init__(self, ansible_info):

        name = ansible_info["tags"]["Name"]
        machine_zone = ansible_info["placement"]["availability_zone"]
        # Look for public IP

        try:
            self.ip_address = ansible_info["network_interfaces"][0][
                "association"]["public_ip"]
        except:
            self.ip_address = None

        super().__init__(name=name,
                         machine_zone=machine_zone,
                         ip_address=self.ip_address)
        self.ansible_info = ansible_info
        self.state = ansible_info["state"]["name"]

    def update_instance_details(self, other):
        super().update_instance_details(other)
        self.ansible_info = other.ansible_info
        self.state = other.state

    def check_online(self):
        return super().check_online() and self.state == "running"

    def install_dependency(self, dependency):
        print("Instance installing: ", dependency)

        uuid = self.update_uuid()
        runner = ansible_runner.run(
            host_pattern=self.name,
            private_data_dir="ansible",
            module="include_role",
            module_args="name=install/{}".format(dependency),
            quiet=monkey_global.QUIET_ANSIBLE,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))

        print(runner.status)
        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Installing Dependency: ", dependency, " failed!")
            return False

        print("Installing Dependency: ", dependency, " succeeded!")
        return True

    def setup_data_item(self, data_item, monkeyfs_path, home_dir_path):

        source_file = os.path.join(monkeyfs_path, "data")
        data_name = data_item["name"]
        data_path = data_item["path"]
        data_checksum = data_item["dataset_checksum"]
        dataset_filename = data_item["dataset_filename"]
        installation_location = os.path.join(home_dir_path, data_item["path"])
        dataset_full_path = os.path.join(monkeyfs_path, "data", data_name,
                                         data_checksum, dataset_filename)
        print("Copying dataset from", dataset_full_path, " to ",
              installation_location)

        uuid = self.update_uuid()
        runner = ansible_runner.run(
            host_pattern=self.name,
            private_data_dir="ansible",
            module="file",
            module_args="path={} state=directory".format(
                installation_location),
            quiet=monkey_global.QUIET_ANSIBLE,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))

        runner = ansible_runner.run(
            host_pattern=self.name,
            private_data_dir="ansible",
            module="unarchive",
            module_args="src={} remote_src=True dest={} creates=yes".format(
                dataset_full_path, installation_location),
            quiet=monkey_global.QUIET_ANSIBLE,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))
        print(runner.stats)
        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Failed to setup data item")
            return False, "Failed to extract archive"

        print("Successfully setup data item")
        return True, "Successfully setup data item"

    def unpack_code_and_persist(self, job_uid, monkeyfs_path, home_dir_path):
        job_path = os.path.join(monkeyfs_path, "jobs", job_uid)

        uuid = self.update_uuid()
        runner = ansible_runner.run(
            host_pattern=self.name,
            private_data_dir="ansible",
            module="copy",
            module_args="src={} dest={} remote_src=true".format(
                job_path + "/", home_dir_path),
            quiet=monkey_global.QUIET_ANSIBLE,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))
        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Failed to copy directory")
            return False, "Failed to copy directory"

        uuid = self.update_uuid()
        runner = ansible_runner.run(
            host_pattern=self.name,
            private_data_dir="ansible",
            module="unarchive",
            module_args="src={} remote_src=True dest={} creates=yes".format(
                os.path.join(job_path, "code.tar"), home_dir_path),
            quiet=monkey_global.QUIET_ANSIBLE,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))
        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Failed to extract archive")
            return False, "Failed to extract archive"

        print("Unpacked code and persisted directory successfully")
        return True, "Unpacked code and persisted directories successfully"

    def setup_persist_folder(self, job_uid, monkeyfs_bucket_name,
                             home_dir_path, persist):
        print("Persisting folder: ", persist)
        persist_path = persist
        persist_name = "." + persist.replace("/", "_") + "_sync.sh"
        script_path = os.path.join(home_dir_path, persist_name)
        monkeyfs_output_folder = \
            os.path.join("/monkeyfs", "jobs", job_uid, persist_path)
        persist_folder_path = os.path.join(home_dir_path, persist_path)

        print("Output folder: ", monkeyfs_output_folder)
        print("Input folder: ", persist_folder_path)

        uuid = self.update_uuid()
        runner = ansible_runner.run(
            host_pattern=self.name,
            private_data_dir="ansible",
            module="include_role",
            module_args="name=aws/configure/persist_folder",
            extravars={
                "persist_folder_path": persist_folder_path,
                "persist_script_path": script_path,
                "bucket_path": monkeyfs_output_folder,
            },
            quiet=monkey_global.QUIET_ANSIBLE,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))

        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Failed to create persisted directory: " + persist_path)
            return False, "Failed to create persisted directory: " + persist_path
        return True, "Setup persist ran successfully"

    def setup_logs_folder(self, job_uid, monkeyfs_bucket_name, home_dir_path):
        print("Persisting logs: ")
        logs_path = os.path.join(home_dir_path, "logs")
        monkeyfs_output_folder = \
            os.path.join("/monkeyfs", "jobs", job_uid, "logs")
        script_path = os.path.join(home_dir_path, ".logs_sync.sh")
        uuid = self.update_uuid()
        runner = ansible_runner.run(
            host_pattern=self.name,
            private_data_dir="ansible",
            module="include_role",
            module_args="name=aws/configure/persist_folder",
            extravars={
                "persist_folder_path": logs_path,
                "persist_script_path": script_path,
                "bucket_path": monkeyfs_output_folder,
                "persist_time": 3,
            },
            quiet=monkey_global.QUIET_ANSIBLE,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))

        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Failed to create persisted logs folder")
            return False, "Failed to create persisted logs folder"
        return True, "Setup logs persistence ran successfully"

    def setup_job(self, job, provider_info=dict()):
        print("Setting up job: ", job)
        job_uid = job["job_uid"]
        credential_file = provider_info.get("aws_cred_file", None)
        aws_storage_name = provider_info["storage_name"]
        monkeyfs_path = provider_info.get("monkeyfs_path", "/monkeyfs")
        if credential_file is None:
            return False, "Service account credential file is not provided"

        print("Mounting filesystem...")
        cred_environment = aws_cred_file_environment(credential_file)

        uuid = self.update_uuid()
        runner = ansible_runner.run(
            host_pattern=self.name,
            private_data_dir="ansible",
            module="include_role",
            module_args="name=aws/mount_fs",
            extravars={
                "aws_storage_name": aws_storage_name,
                "monkeyfs_path": monkeyfs_path,
                "access_key_id": cred_environment["AWS_ACCESS_KEY_ID"],
                "access_key_secret": cred_environment["AWS_SECRET_ACCESS_KEY"]
            },
            quiet=monkey_global.QUIET_ANSIBLE,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))
        print(runner.stats)
        if runner.status == "failed" or self.get_uuid() != uuid:
            print("Failed to mount filesystem")
            return False, "Failed to mount filesystem"

        home_dir_path = "/home/ubuntu"

        for data_item in job.get("data", []):
            print("Setting up data item", data_item)
            success, msg = self.setup_data_item(data_item=data_item,
                                                monkeyfs_path=monkeyfs_path,
                                                home_dir_path=home_dir_path)
            if success == False:
                return success, msg

        success, msg = self.unpack_code_and_persist(
            job_uid=job_uid,
            monkeyfs_path=monkeyfs_path,
            home_dir_path=home_dir_path)
        if success == False:
            return success, msg
        print("Success in unpacking all datasets")

        print("Setting up logs folder")
        success, msg = self.setup_logs_folder(
            job_uid=job_uid,
            monkeyfs_bucket_name=aws_storage_name,
            home_dir_path=home_dir_path)
        if success == False:
            return success, msg

        for persist_item in job.get("persist", []):
            print("Setting up persist item", persist_item)
            success, msg = self.setup_persist_folder(
                job_uid=job_uid,
                monkeyfs_bucket_name=aws_storage_name,
                home_dir_path=home_dir_path,
                persist=persist_item)
            if success == False:
                return success, msg

        print("Setting up dependency manager...")
        success, msg = self.setup_dependency_manager(job["run"])
        if success == False:
            return success, msg

        return True, "Successfully setup the job"

    def setup_dependency_manager(self, run_yml):
        env_type = run_yml["env_type"]
        env_file = run_yml["env_file"]
        print("Env type: ", env_type)
        print("Env file: ", env_file)

        uuid = self.update_uuid()
        if env_type == "conda":
            runner = ansible_runner.run(
                host_pattern=self.name,
                private_data_dir="ansible",
                module="include_role",
                module_args="name=run/setup_conda",
                extravars={
                    "environment_file": env_file,
                },
                quiet=monkey_global.QUIET_ANSIBLE,
                cancel_callback=self.ansible_runner_uuid_cancel(uuid))
        elif env_type == "pip":
            runner = ansible_runner.run(
                host_pattern=self.name,
                private_data_dir="ansible",
                module="include_role",
                module_args="name=run/setup_pip",
                extravars={
                    "environment_file": env_file,
                },
                quiet=monkey_global.QUIET_ANSIBLE,
                cancel_callback=self.ansible_runner_uuid_cancel(uuid))
        elif env_type == "docker":
            runner = ansible_runner.run(
                host_pattern=self.name,
                private_data_dir="ansible",
                module="include_role",
                module_args="name=run/setup_docker",
                extravars={
                    "environment_file": env_file,
                },
                quiet=monkey_global.QUIET_ANSIBLE,
                cancel_callback=self.ansible_runner_uuid_cancel(uuid))
        else:
            return False, "Provided or missing dependency manager"

        if runner.status == "failed" or self.get_uuid() != uuid:
            return False, "Failed to initialize environment manager"

        return True, "Successfully created dependency manager and stored initialization in .monkey_activate"

    def execute_command(self, cmd, run_yml):
        print("Executing cmd: ", cmd)
        print("Environment Variables:", run_yml.get("env", dict()))
        final_command = ". ~/.monkey_activate; " + cmd + " 2>&1 | tee logs/run.log"

        uuid = self.update_uuid()
        runner = ansible_runner.run(
            host_pattern=self.name,
            private_data_dir="ansible",
            module="include_role",
            module_args="name=run/cmd",
            extravars={"run_command": cmd},
            envvars=run_yml.get("env", dict()),
            quiet=monkey_global.QUIET_ANSIBLE,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))

        print(runner.stats)
        events = list(runner.events)
        if runner.status == "failed" or self.get_uuid() != uuid:
            return False, "Failed to run command properly: " + cmd

        return True, "Successfully ran job"

    def run_job(self, job, provider_info=dict()):
        print("Running job: ", job)
        job_uid = job["job_uid"]
        credential_file = provider_info.get("aws_cred_file", None)
        aws_storage_name = provider_info["storage_name"]
        monkeyfs_path = provider_info.get("monkeyfs_path", "/monkeyfs")
        if credential_file is None:
            return False, "AWS Account Credential file is not provided"

        success, msg = self.execute_command(cmd=job["cmd"], run_yml=job["run"])
        if success == False:
            return success, msg

        print("\n\nRan job:", job_uid, " SUCCESSFULLY!\n\n")

        return True, "Job completed"

    def cleanup_job(self, job, provider_info=dict()):
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

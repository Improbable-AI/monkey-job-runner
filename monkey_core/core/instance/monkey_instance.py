import logging
import os
import threading
from concurrent.futures import Future
from datetime import datetime
from threading import Thread
from uuid import uuid1

import ansible_runner
import requests
from core.monkey_global import QUIET_ANSIBLE

logger = logging.getLogger(__name__)

HEARTBEAT_TIME = 30
HEARTBEAT_FAILURE_TOLERANCE = 3


class AnsibleRunException(Exception):
    pass


class MonkeyInstance():

    name = None
    creation_time = None
    destruction_time = None
    ip_address = None
    state = None
    lock = threading.Lock()
    additional_extravars = dict()

    offline_count = 0
    offline_retries = 3
    last_uuid = None

    def __init__(self, name, ip_address):
        super().__init__()
        self.name = name
        self.ip_address = ip_address
        self.creation_time = datetime.now()
        # threading.Thread(target=self.heartbeat_loop, daemon=True)

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        return self.creation_time < other.creation_time

    def check_online(self):
        if self.ip_address is None:
            return False
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

    def update_instance_details(self, other):
        self.name = other.name
        self.ip_address = other.ip_address

    def get_uuid(self):
        with self.lock:
            uuid = self.last_uuid
        return uuid

    def update_uuid(self):
        with self.lock:
            new_uuid = uuid1()
            self.last_uuid = new_uuid
        return new_uuid

    def ansible_runner_uuid_cancel(self, uuid):

        def check_for_uuid_change():
            change = self.last_uuid != uuid
            # print("Checking uuid: {} != {}, : {}".format(
            # self.last_uuid, uuid, change))
            return change

        return check_for_uuid_change

    def check_uuid(self, uuid):
        check = False
        with self.lock:
            if self.last_uuid == uuid:
                check = True
        return check

    def get_experiment_hyperparameters(self):
        if self.ip_address is None:
            return None
        try:
            r = requests.get("http://{}:9991/config".format(self.ip_address),
                             timeout=4)
            r.raise_for_status()
            result = r.json()
            if result['ok']:
                return result['data']
            else:
                return None
        except:
            return None

    def print_failed_event(self, runner):
        events = list(runner.events)[-10:]
        for e in events:
            event_data = e.get("event_data", dict())
            print("TASK-----------------------------")
            print(e)
            print(event_data.get("task", "unknown name"))
            print("STDOUT:")
            print(e.get("stdout", "no stdout"))
            print("TASK ACTION: " + event_data.get("task_action", "unknown"))
            print("TASK ARGS: " + event_data.get("task_args", "unknown"))
            print("TASK PATH: " + event_data.get("task_path", "unknown"))
            print("\n")

    def run_ansible_role_inexclusively(self,
                                       rolename,
                                       extravars=dict(),
                                       envvars=dict(),
                                       cancel_callback=None):
        extravars.update(self.additional_extravars)
        runner = ansible_runner.run(host_pattern=self.name,
                                    private_data_dir="ansible",
                                    module="include_role",
                                    module_args=f"name={rolename}",
                                    quiet=QUIET_ANSIBLE,
                                    extravars=extravars,
                                    envvars=envvars,
                                    cancel_callback=cancel_callback)
        return runner

    def run_ansible_role(self, rolename, extravars=dict(), envvars=dict()):
        uuid = self.update_uuid()
        runner = self.run_ansible_role_inexclusively(
            rolename=rolename,
            extravars=extravars,
            envvars=envvars,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))

        if self.get_uuid() != uuid:
            raise AnsibleRunException(
                "Running ansible role cancelled due to concurrency")

        if runner.status == "failed":
            self.print_failed_event(runner=runner)
            raise AnsibleRunException("Ansible role failed to run")

    def run_ansible_module_inexclusively(self,
                                         modulename,
                                         args,
                                         cancel_callback=None):
        args_string = args
        if type(args) is dict:
            args_string = ""
            for key, val in args.items():

                args_string += f"{key}={val} "
        runner = ansible_runner.run(host_pattern=self.name,
                                    private_data_dir="ansible",
                                    module=modulename,
                                    module_args=args_string,
                                    quiet=QUIET_ANSIBLE,
                                    cancel_callback=cancel_callback)
        return runner

    def run_ansible_module(self, modulename, args=""):
        uuid = self.update_uuid()
        runner = self.run_ansible_module_inexclusively(
            modulename=modulename,
            args=args,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))

        if self.get_uuid() != uuid:
            raise AnsibleRunException(
                "Running ansible cancelled due to concurrency")

        if runner.status == "failed":
            self.print_failed_event(runner=runner)
            raise AnsibleRunException("Ansible module failed to run")

    def run_ansible_playbook_inexclusively(self,
                                           playbook,
                                           extravars,
                                           cancel_callback=None):
        extravars.update(self.additional_extravars)
        runner = ansible_runner.run(host_pattern=self.name,
                                    playbook=playbook,
                                    private_data_dir="ansible",
                                    extravars=extravars,
                                    quiet=QUIET_ANSIBLE,
                                    cancel_callback=cancel_callback)
        return runner

    def run_ansible_playbook(self, playbook, extravars):
        uuid = self.update_uuid()
        runner = self.run_ansible_playbook_inexclusively(
            playbook=playbook,
            extravars=extravars,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))

        if self.get_uuid() != uuid:
            raise AnsibleRunException(
                "Running ansible cancelled due to concurrency")

        if runner.status == "failed":
            self.print_failed_event(runner=runner)
            raise AnsibleRunException("Ansible module failed to run")

    def run_ansible_shell_inexclusively(self, command, cancel_callback=None):
        args = f"cmd='{command}' executable=/bin/bash"
        print(f"Running in shell: {args}")
        runner = ansible_runner.run(host_pattern=self.name,
                                    private_data_dir="ansible",
                                    module="shell",
                                    module_args=f'/bin/bash -c "{command}"',
                                    quiet=QUIET_ANSIBLE,
                                    cancel_callback=cancel_callback)
        return runner

    def run_ansible_shell(self, command, printout=False):
        uuid = self.update_uuid()
        runner = self.run_ansible_shell_inexclusively(
            command=command,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))
        if self.get_uuid() != uuid:
            raise AnsibleRunException(
                "Running ansible cancelled due to concurrency")

        if runner.status == "failed":
            self.print_failed_event(runner=runner)
            raise AnsibleRunException("Ansible module failed to run")
        if printout:
            self.print_failed_event(runner)

    from core.instance.monkey_instance_shared import (execute_command, run_job,
                                                      setup_data_item,
                                                      setup_dependency_manager,
                                                      setup_logs_folder,
                                                      setup_persist_folder,
                                                      start_persist,
                                                      unpack_code_and_persist,
                                                      unpack_job_dir)

    def mount_monkeyfs(self, job_yml, provider_info):
        raise NotImplementedError("This is not implemented yet")

    def setup_job(self, job_yml, provider_info=dict()):
        """
        Setup data item
        Unpacks Job Dir
        Unpacks Code
        Setup Log Folder
        Persist all folders
        Start persisting
        Setup Dependency manager
        """
        print("Setting up job: ", job_yml)
        job_uid = job_yml["job_uid"]

        for data_item in job_yml.get("data", []):
            print("Setting up data item", data_item)
            success, msg = self.setup_data_item(
                job_uid=job_uid,
                data_item=data_item,
            )
            if not success:
                return success, msg

        success, msg = self.unpack_job_dir(job_uid=job_uid)
        if not success:
            return success, msg

        for code_item in job_yml.get("code", []):
            success, msg = self.unpack_code_and_persist(
                job_uid=job_uid,
                code_item=code_item,
            )
            if not success:
                return success, msg
            print("Success in unpacking all codebase items")

        print("Setting up logs folder")
        success, msg = self.setup_logs_folder(job_uid=job_uid)
        if not success:
            return success, msg

        for persist_item in job_yml.get("persist", []):
            print("Setting up persist item", persist_item)
            success, msg = self.setup_persist_folder(
                job_uid=job_uid,
                persist=persist_item,
            )
            if not success:
                return success, msg

        print("Starting Persist")
        success, msg = self.start_persist(job_uid=job_uid,)
        if not success:
            return success, msg

        print("Setting up dependency manager...")
        success, msg = self.setup_dependency_manager(
            job_uid=job_uid,
            run_yml=job_yml["run"],
        )
        if not success:
            return success, msg

        return True, "Successfully setup the job"

    def install_dependency(self, dependency):
        logger.info(f"Instance installing: {dependency}")

        try:
            self.run_ansible_role(rolename=f"setup/install/{dependency}")
        except AnsibleRunException as e:
            print(e)
            logger.error(f"Installing Dependency: {dependency} failed")
            return False

        logger.info(f"Installing Dependency: {dependency} succeeded!")
        return True

    def cleanup_job(self, job_yml, provider_info=dict()):
        raise NotImplementedError("This is not implemented yet")

    def get_monkeyfs_dir(self):
        raise NotImplementedError("This is not implemented yet")

    def get_scratch_dir(self):
        raise NotImplementedError("This is not implemented yet")

    def get_job_dir(self, job_uid):
        return os.path.join(self.get_scratch_dir(), job_uid, "")

    def get_monkeyfs_job_dir(self, job_uid):
        return os.path.join(self.get_monkeyfs_dir(), "jobs", job_uid, "")

    def get_dataset_path(self, data_name, checksum, extension):
        return os.path.join(
            self.get_monkeyfs_dir(),
            "data",
            data_name,
            checksum,
            "data" + extension,
        )

    def get_codebase_path(self, run_name, checksum, extension):
        return os.path.join(
            self.get_monkeyfs_dir(),
            "code",
            run_name,
        )

    def get_codebase_file_path(self, run_name, checksum, extension):
        return os.path.join(
            self.get_monkeyfs_dir(),
            "code",
            run_name,
            checksum,
            "code" + extension,
        )

    def get_persist_all_script(self, job_uid):
        return os.path.join(
            self.get_job_dir(job_uid=job_uid),
            "sync",
            "persist_all.sh",
        )

    def get_unique_persist_all_script_name(self, job_uid):
        return job_uid + "_persist_all_loop.sh"

    def get_monkey_activate_file(self, job_uid):
        return os.path.join(
            self.get_job_dir(job_uid=job_uid),
            ".monkey_activate",
        )

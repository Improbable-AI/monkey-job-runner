import logging
import os

import ansible_runner
import requests
import yaml
from core.instance.monkey_instance import AnsibleRunException, MonkeyInstance

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

        try:
            self.run_ansible_role(
                rolename="local/setup/machine",
                extravars=self.provider.get_local_vars(),
            )

        except Exception as e:
            print(e)
            print("Failed to setup machine")
            return False

        return True

    def check_online(self):
        return True
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
        monkeyfs_scratch = local_vars.get("monkeyfs_scratch")
        return monkeyfs_scratch

    def get_monkeyfs_dir(self):
        local_vars = self.provider.get_local_vars()
        monkeyfs_path = local_vars.get("monkeyfs_path")
        return monkeyfs_path

        return True, "Job completed"

    def cleanup_job(self, job_yml, provider_info={}):
        job_uid = job_yml["job_uid"]
        print("\n\nTerminating Machine:", job_uid, "\n\n")
        unique_persist_all_script_name = self.get_unique_persist_all_script_name(
            job_uid=job_uid)
        try:
            print(f"Run CMD: 'killall {unique_persist_all_script_name}'")
            self.run_ansible_shell(
                command=f"killall {unique_persist_all_script_name}",
                printout=True)
        except Exception as e:
            print(e)
            print("Failed to cancel sync loop")
        return True, "Succesfully cleaned up job"

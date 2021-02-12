import logging
import os
import subprocess
import threading
from concurrent.futures import Future
from datetime import datetime, timedelta

import monkey_global
import yaml
from setup_scripts.utils import (aws_cred_file_environment, printout_ansible_events)

from core.monkey_instance_local import MonkeyInstanceLocal
from core.monkey_provider import MonkeyProvider

logger = logging.getLogger(__name__)
logging.getLogger("botocore").setLevel(logging.WARNING)


class MonkeyProviderLocal(MonkeyProvider):

    raw_provider_info = dict()
    instances = dict()
    last_instance_fetch = datetime.now() - timedelta(minutes=10)
    instance_list_refresh_period = 10

    def get_dict(self):
        res = super().get_dict()
        for key, value in self.raw_provider_info.items():
            res[key] = value
        return res

    def __init__(self, provider_info):
        super().__init__(provider_info)
        self.provider_type = "local"
        self.provider_info = provider_info

        for key, value in provider_info.items():
            if value is not None:
                self.raw_provider_info[key] = value

        logger.info("Local Handler Instantiating {}".format(self.name))

        self.check_filesystem_existence()
        # TODO(alamp): Dispatch in backgorund thread to allow no stall monkey_core start
        self.load_monkey_instances()
        # threading.Thread(target=self.load_monkey_instances).start()

    def get_local_vars(self):
        with open("ansible/local_vars.yml", 'r') as local_vars_file:
            local_vars = yaml.full_load(local_vars_file)
            return local_vars

    def check_filesystem_existence(self):
        # Check for mounts
        print("Checking for mounted filesystem")
        local_monkeyfs_path = self.provider_info.get("local_monkeyfs_path",
                                                     f"ansible/monkeyfs")
        print(f"running: stat {local_monkeyfs_path}")

        fs_output = subprocess.run(f"stat {local_monkeyfs_path}",
                                   check=False,
                                   shell=True,
                                   capture_output=True).stdout.decode("utf-8")
        print("Check filesystem mounted printout: ", fs_output)
        if fs_output is not None and fs_output != "":
            return True
        os.makedirs(local_monkeyfs_path, exist_ok=True)
        return True

    def load_monkey_instances(self):
        print("Loading monkey instances")
        try:
            with open("local.yml", "r") as local_yaml_file:
                local_yaml = yaml.full_load(local_yaml_file)
                local_hosts = local_yaml.get("hosts", [])
                hostnames = [x[0] for x in local_hosts]
                for hostname in hostnames:
                    inst = self.create_local_instance(name=hostname, hostname=hostname)
                    self.instances[inst.name] = inst

                print(local_yaml)
                print("Instances Registered: ")
                for hostname, inst in self.instances.items():
                    print(f"{hostname}: {inst}")

        except Exception as e:
            print(f"Exception found: {e}")

    def check_provider(self):
        return True

    def create_local_instance(self, name, hostname=None):
        print(
            f"Creating instance with name: {name }, hostname: {hostname if hostname is not None else name}"
        )
        if hostname is None:
            instance = MonkeyInstanceLocal(provider=self, name=name, hostname=name)
        else:
            instance = MonkeyInstanceLocal(provider=self, name=name, hostname=hostname)
        return instance

    def is_valid(self):
        return super().is_valid()

    def get_local_filesystem_path(self):
        return self.raw_provider_info["local_monkeyfs_path"]

    def get_local_instances_list(self):
        return sorted(list(self.instances.keys()))

    def check_connection(self):
        pass

    def list_instances(self):
        return sorted(list(self.instances.values()))

    def get_instance(self, instance_name):
        """Attempts to get instance by name

        Args:
            instance_name (str): The job_uid or name of instance

        Returns:
            [MonkeyInstance]: MonkeyInstance if it exists otherwise None
        """
        instances = self.list_instances()
        for instance in instances:
            if instance.name == instance_name:
                return instance
        found_instance = None

        return found_instance

    def list_jobs(self):
        jobs = []
        # for zone in self.zones:
        #     try:
        #         result = self.compute_api.instances().list(
        #             project=self.project, zone=zone).execute()
        #         result = result['items'] if 'items' in result else None
        #         if result:
        #             for item in result:
        #                 labels = item['labels'] if 'labels' in item else []
        #                 monkey_identifier_target = self.machine_defaults[
        #                     'monkey-identifier']
        #                 if 'monkey-identifier' in labels and labels[
        #                         'monkey-identifier'] == monkey_identifier_target:
        #                     jobs.append(item['name'])
        #     except:
        #         pass
        return jobs

    def list_images(self):
        images = []
        try:
            result = self.compute_api.images().list(project=self.project).execute()
            result = result['items'] if 'items' in result else None
            if result:
                images += [(inst["name"], inst["family"] if "family" in inst else None)
                           for inst in result]
        except:
            pass

        return images

    def create_instance(self, machine_params=dict(), job_yml=dict()):
        print("Looking for existing local instance to dispatch")
        instance = job_yml.get("instance", None)
        if instance is None:
            return None, False
        print(self.instances)
        for hostname, inst in self.instances.items():
            if hostname == instance:
                return inst, True

        return None, False

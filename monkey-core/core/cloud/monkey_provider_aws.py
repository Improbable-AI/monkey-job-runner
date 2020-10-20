import logging
import os
import subprocess
import time
from concurrent.futures import Future
from datetime import datetime, timedelta
from threading import Thread

import ansible_runner
import monkey_global
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from core.cloud.monkey_instance_aws import MonkeyInstanceAWS
from core.monkey_provider import MonkeyProvider
from setup_scripts.utils import (aws_cred_file_environment,
                                 printout_ansible_events)

logger = logging.getLogger(__name__)
logging.getLogger("botocore").setLevel(logging.WARNING)


class MonkeyProviderAWS(MonkeyProvider):

    raw_provider_info = dict()
    instances = dict()
    last_instance_fetch = datetime.now() - timedelta(minutes=10)
    instance_list_refresh_period = 10

    def get_dict(self):
        res = super().get_dict()
        res["credential_file"] = self.credential_file
        for key, value in self.raw_provider_info.items():
            res[key] = value
        return res

    def __init__(self, provider_info):
        super().__init__(provider_info)
        self.provider_type = "aws"
        self.zone = provider_info["aws_zone"]
        provider_info["zone"] = provider_info["aws_zone"]
        self.provider_info = provider_info

        for key, value in provider_info.items():
            if value is not None:
                self.raw_provider_info[key] = value

        logger.info("AWS Cloud Handler Instantiating {}".format(self.name))
        if "aws_cred_file" not in provider_info:
            logger.error("Failed to provider aws_cred_file for account")
            raise ValueError("Failed to provider aws_cred_file for account")

        self.credential_file = provider_info["aws_cred_file"]
        cred_environment = aws_cred_file_environment(self.credential_file)
        for key, value in cred_environment.items():
            os.environ[key] = value

        if self.check_filesystem_mounted() == False:
            print("Filesystem mount not found")
            print("Remounting filesystem.... ")
            if self.check_provider() == False or self.check_filesystem_mounted(
            ):
                print("Failed to remount filesystem")
                return None
            else:
                print("Filesystem remounted successfully!")

    def check_filesystem_mounted(self):
        # Check for mounts
        print("Checking for mounted filesystem")

        fs_output = subprocess.run("df {} | grep monkeyfs".format(
            self.provider_info.get("local_monkeyfs_path",
                                   "ansible/monkeyfs-aws")),
                                   shell=True,
                                   capture_output=True).stdout.decode("utf-8")
        if fs_output is not None and fs_output != "":
            return (fs_output.split()[0] == "s3fs"
                    or fs_output.split()[0] == self.provider_info.get(
                        "storage_name", "monkeyfs"))
        return False

    def check_provider(self):
        cred_environment = aws_cred_file_environment(
            self.provider_info["aws_cred_file"])

        runner = ansible_runner.run(
            playbook='aws_setup_checks.yml',
            private_data_dir='ansible',
            extravars={
                "access_key_id": cred_environment["AWS_ACCESS_KEY_ID"],
                "access_key_secret": cred_environment["AWS_SECRET_ACCESS_KEY"],
            },
            quiet=True)

        events = [e for e in runner.events]
        if runner.status == "failed":
            print("Failed to mount the AWS S3 filesystem")
            return False
        print("Mount successful")
        return True

    def is_valid(self):
        return super().is_valid()

    def get_local_filesystem_path(self):
        return self.raw_provider_info["local_monkeyfs_path"]

    def check_connection(self):
        pass

    def list_instances(self):
        if (datetime.now() - self.last_instance_fetch
            ).total_seconds() < self.instance_list_refresh_period:
            return sorted(list(self.instances.values()))
        # MARK(alamp): AnsibleInternalAPI
        loader = DataLoader()
        inventory = InventoryManager(loader=loader,
                                     sources="ansible/inventory")
        host_list = inventory.get_groups_dict().get("monkey_aws", [])
        detected_instances = []
        for host in host_list:
            h = inventory.get_host(host)
            host_vars = h.get_vars()
            inst = MonkeyInstanceAWS(ansible_info=host_vars)
            detected_instances.append(inst)

        detected_names = set([x.name for x in detected_instances])
        for detected_instance in detected_instances:
            if detected_instance.name in self.instances:
                self.instances[detected_instance.name].update_instance_details(
                    detected_instance)
            else:
                self.instances[detected_instance.name] = detected_instance

        offline_instances = set(
            self.instances.keys()).difference(detected_names)
        for offline_instance in offline_instances:
            self.instances[offline_instance].state = "offline"

        self.last_instance_fetch = datetime.now()
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
        for zone in self.zones:
            try:
                result = self.compute_api.instances().list(
                    project=self.project, zone=zone).execute()
                result = result['items'] if 'items' in result else None
                if result:
                    for item in result:
                        labels = item['labels'] if 'labels' in item else []
                        monkey_identifier_target = self.machine_defaults[
                            'monkey-identifier']
                        if 'monkey-identifier' in labels and labels[
                                'monkey-identifier'] == monkey_identifier_target:
                            jobs.append(item['name'])
            except:
                pass
        return jobs

    def list_images(self):
        images = []
        try:
            result = self.compute_api.images().list(
                project=self.project).execute()
            result = result['items'] if 'items' in result else None
            if result:
                images += [(inst["name"],
                            inst["family"] if "family" in inst else None)
                           for inst in result]
        except:
            pass

        return images

    def create_instance(self, machine_params=dict()):
        print("MACHINE PARAMS: ", machine_params)

        runner = ansible_runner.run(playbook='aws_create_job.yml',
                                    private_data_dir='ansible',
                                    extravars=machine_params,
                                    quiet=monkey_global.QUIET_ANSIBLE)
        print(runner.stats)

        if runner.status == "failed":
            print("Failed to create the instance")
            return None, False
        retries = 1
        while retries > 0:
            loader = DataLoader()
            inventory = InventoryManager(loader=loader,
                                         sources="ansible/inventory")
            try:
                print("Checking inventory for host machine")
                h = inventory.get_host(machine_params["monkey_job_uid"])
                host_vars = h.get_vars()
                inst = MonkeyInstanceAWS(ansible_info=host_vars)
                print(inst)
                # TODO ensure machine is on
                if inst is not None and inst.check_online():
                    print("Instance found online")
                    if inst.name in self.instances:
                        self.instances[inst.name].update_instance_details(inst)
                    else:
                        print("Adding to provider instances")
                        self.instances[inst.name] = inst

                    return inst, True
            except Exception as e:
                print("Failed to get host", e)
                return None, False
            retries -= 1
            print("Retry inventory creation for machine")
            time.sleep(2)
        return None, False

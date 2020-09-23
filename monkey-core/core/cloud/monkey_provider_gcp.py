import datetime
import json
import logging
import random
import string
import time
from concurrent.futures import Future
from threading import Thread

import ansible_runner
import googleapiclient.discovery
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from core.cloud.monkey_instance_gcp import MonkeyInstanceGCP
from core.monkey_provider import MonkeyProvider
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("google.auth.transport.requests").setLevel(logging.WARNING)


class MonkeyProviderGCP(MonkeyProvider):
    compute_api = None
    credentials = None
    raw_provider_info = dict()

    def get_dict(self):
        res = {
            "name": self.name,
            "type": self.provider_type,
            "credential_file": self.credential_file,
        }
        for key, value in self.raw_provider_info.items():
            res[key] = value
        return res

    def __init__(self, provider_info):
        print("Initializing... GCP")
        super().__init__(provider_info)
        self.provider_type = "gcp"
        self.zone = provider_info["gcp_zone"]
        self.project = provider_info["project"]

        provider_info["zone"] = provider_info["gcp_zone"]
        for key, value in provider_info.items():
            if value is not None:
                self.raw_provider_info[key] = value

        logger.info("GCP Cloud Handler Instantiating {}".format(self))
        if "gcp_cred_file" not in provider_info:
            logger.error("Failed to provide gcp_cred_file for service account")
            raise ValueError(
                "Failed to provide gcp_cred_file for service account")

        self.credential_file = provider_info["gcp_cred_file"]
        self.credentials = service_account.Credentials.from_service_account_file(
            provider_info["gcp_cred_file"])
        self.compute_api = googleapiclient.discovery.build(
            'compute',
            'v1',
            credentials=self.credentials,
            cache_discovery=False)

    def is_valid(self):
        # Check filesystem

        # Check permissions

        return super().is_valid() and self.credentials is not None

    def get_local_filesystem_path(self):
        return self.raw_provider_info["local_monkeyfs_path"]

    def check_connection(self):
        try:
            result = self.compute_api.instances().list(
                project=self.project, zone=self.zones[0]).execute()
            result = result['items'] if 'items' in result else None
            if result:
                return True
        except:
            pass
        return False

    def list_instances(self):
        instances = []
        # MARK(alamp): AnsibleInternalAPI
        loader = DataLoader()
        inventory = InventoryManager(loader=loader,
                                     sources="ansible/inventory")
        variable_manager = VariableManager(loader=loader, inventory=inventory)
        host_list = inventory.get_groups_dict().get("monkey_gcp", [])
        for host in host_list:
            h = inventory.get_host(host)
            host_vars = h.get_vars()
            inst = MonkeyInstanceGCP(ansible_info=host_vars)
            instances.append(inst)
        return instances

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

        runner = ansible_runner.run(playbook='gcp_create_job.yml',
                                    private_data_dir='ansible',
                                    extravars=machine_params)
        print(runner.stats)

        if len(runner.stats.get("failures")) != 0:
            return None, False
        print(machine_params)
        retries = 4
        while retries > 0:
            loader = DataLoader()
            inventory = InventoryManager(loader=loader,
                                         sources="ansible/inventory")
            try:
                h = inventory.get_host(machine_params["monkey_job_uid"])
                host_vars = h.get_vars()
                inst = MonkeyInstanceGCP(ansible_info=host_vars)
                # TODO ensure machine is on
                if inst is not None:
                    return inst, True
            except Exception as e:
                print("Failed to get host", e)
                return None, False
            retries -= 1
            print("Retry inventory creation for machine")
            time.sleep(2)
        return None, False

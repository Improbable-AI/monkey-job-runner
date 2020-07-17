
import json
import time
import random
import string
import datetime

import logging 
logger = logging.getLogger(__name__)

from google.oauth2 import service_account
import googleapiclient.discovery

from core.monkey_instance import MonkeyInstanceGCP

from threading import Thread
from concurrent.futures import Future
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager
from ansible.vars.manager import VariableManager
import ansible_runner
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("google.auth.transport.requests").setLevel(logging.WARNING)

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

class MonkeyProvider():

    credential_file = None
    zone = None
    project = None
    name = None
    provider_type = None
    instances = []

    def merge_params(self, base, additional):
        for key, value in additional.items():
            if key in base and type(base[key]) == list:
                base[key] += value
            else:
                base[key] = value
        return base

    @staticmethod
    def create_cloud_handler(provider_info):
        provider_type = provider_info["type"]
        if provider_type == "gcp":
            return MonkeyProviderGCP(provider_info)
        else:
            raise ValueError("{} type for provider not supported yet".format(provider_type))

    def __init__(self, provider_info):
        super().__init__()
        self.name = provider_info["name"]
        self.zone = provider_info["zone"]
        self.project = provider_info["project"]

    def list_instances(self):
        raise NotImplementedError("This is not implemented yet")

    def get_instance(self, instance_name):
        raise NotImplementedError("This is not implemented yet")

    def list_jobs(self):
        raise NotImplementedError("This is not implemented yet")

    def list_images(self):
        raise NotImplementedError("This is not implemented yet")

    def create_instance(self, machine_params):
        raise NotImplementedError("This is not implemented yet")

    def wait_for_operation(self, operation_name):
        raise NotImplementedError("This is not implemented yet")

    def check_connection(self):
        raise NotImplementedError("This is not implemented yet")

    def is_valid(self):
        return not(self.credentials == None or \
            self.zone == None or \
            self.project == None or \
            self.name == None or \
            self.provider_type == None)

    def __str__(self):
        return "Name: {}, provider: {}, zone: {}, project: {}"\
            .format(self.name, self.provider_type,self.zone, self.project)

    def get_dict(self):
        return {
            "name": self.name,
            "type": self.provider_type
        }
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
        super().__init__(provider_info)
        self.provider_type = "gcp"
        for key, value in provider_info.items():
            if value is not None:
                self.raw_provider_info[key] = value

        logger.info("GCP Cloud Handler Instantiating {}".format(self))
        if "gcp_cred_file" not in provider_info:
            logger.error("Failed to provide gcp_cred_file for service account")
            raise ValueError("Failed to provide gcp_cred_file for service account")
        
        self.credential_file = provider_info["gcp_cred_file"]
        self.credentials = service_account.Credentials.from_service_account_file(provider_info["gcp_cred_file"])
        self.compute_api = googleapiclient.discovery.build('compute', 'v1', credentials=self.credentials, cache_discovery=False)


    def is_valid(self):
        return super().is_valid() and self.credentials is not None
     
    def check_connection(self):
        try:
            result = self.compute_api.instances().list(project=self.project, zone=self.zones[0]).execute()
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
        inventory = InventoryManager(loader=loader, sources="ansible/inventory")
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
                result = self.compute_api.instances().list(project=self.project, zone=zone).execute()
                result = result['items'] if 'items' in result else None
                if result:
                    for item in result:
                        labels = item['labels'] if 'labels' in item else  []
                        monkey_identifier_target = self.machine_defaults['monkey-identifier']
                        if 'monkey-identifier' in labels and labels['monkey-identifier'] == monkey_identifier_target:
                            jobs.append(item['name'])
            except: 
                pass
        return jobs

    def list_images(self):
        images = []
        try:
            result = self.compute_api.images().list(project=self.project).execute()
            result = result['items'] if 'items' in result else None
            if result:
                images += [(inst["name"], inst["family"] if "family" in inst else None) for inst in result]
        except: 
            pass
            
        return images
    
    def create_instance(self, machine_params=dict()):
  
        runner = ansible_runner.run(playbook='gcp_create_job.yml', private_data_dir='ansible', extravars=machine_params)
        print(runner.stats)

        
        if len(runner.stats.get("failures")) != 0:
            return None, False
        print(machine_params)
        retries = 4
        while retries > 0:
            loader = DataLoader()
            inventory = InventoryManager(loader=loader, sources="ansible/inventory")
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



import json
import time
import random
import string
import datetime

import logging 
logger = logging.getLogger(__name__)

from google.oauth2 import service_account
import googleapiclient.discovery


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
            from core.cloud.monkey_provider_gcp import MonkeyProviderGCP            
            return MonkeyProviderGCP(provider_info)
        elif provider_type == "aws":
            return MonkeyProviderAWS(provider_info)
        else:
            raise ValueError("{} type for provider not supported yet".format(provider_type))

    def __init__(self, provider_info):
        super().__init__()
        self.name = provider_info["name"]
        self.project = provider_info["project"]

    def get_local_filesystem_path(self):
        raise NotImplementedError("This is not implemented yet")

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




import json
import time
import random
import string
import datetime

import logging 
logger = logging.getLogger(__name__)

class MonkeyInstance():

    machine_name = None
    machine_zone = None
    machine_project = None
    creation_time = None
    destruction_time = None
    ip_address = None

    def __init__(self):
        super().__init__()

    def destroy_instance(self):
        raise NotImplementedError("This is not implemented yet")

    def stop_instance(self):
        raise NotImplementedError("This is not implemented yet")
    


class MonkeyInstanceGCP(MonkeyInstance):

#   Can construct a Monkey Instance from either creation operaion or ip address
    def __init__(self,  machine_name=None, machine_zone=None, machine_project=None, ip_address=None, creation_operation_name=None):
        super().__init__()
        

    @classmethod
    def from_creation_operation(machine_name=None, machine_zone=None, machine_project=None, creation_operation_name=None):
        return MonkeyInstanceGCP(machine_name=machine_name, machine_zone=machine_zone, machine_project=machine_project, creation_operation_name=creation_operation_name)
        

    @classmethod
    def from_ip_address(ip_address=None, retries=4, retry_time=2):
        
        #  TODO fetch info from ip address

        return MonkeyInstanceGCP(machine_name=None, machine_zone=None, machine_project=None, ip_address=ip_address)

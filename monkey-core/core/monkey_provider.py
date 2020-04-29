
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

    credentials = None
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

    def list_jobs(self):
        raise NotImplementedError("This is not implemented yet")

    def list_images(self):
        raise NotImplementedError("This is not implemented yet")

    def create_instance(self, machine_params, wait_for_monkey_client=False):
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
    
    def __init__(self, provider_info):
        super().__init__(provider_info)
        self.provider_type = "gcp"
        # Overrides if type is the same
        # if "gcp" in default_params:
        #     self.machine_defaults = self.merge_params(self.machine_defaults, default_params["gcp"])
        # # Overrides if name matches
        # if self.name in default_params:
        #     self.machine_defaults = self.merge_params(self.machine_defaults, default_params[self.name])

        logger.info("GCP Cloud Handler Instantiating {}".format(self))
        if "gcp_cred_file" not in provider_info:
            logger.error("Failed to provide gcp_cred_file for service account")
            raise ValueError("Failed to provide gcp_cred_file for service account")
        
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
        inventory = InventoryManager(loader=loader, sources="/Users/avery/Developer/projects/monkey-project/monkey-core/ansible/inventory")
        variable_manager = VariableManager(loader=loader, inventory=inventory)
        host_list = inventory.get_groups_dict()["monkey_gcp"]
        for host in host_list:
            h = inventory.get_host(host)
            host_vars = h.get_vars()
            inst = MonkeyInstanceGCP(ansible_info=host_vars)
            instances.append(inst)
        return instances
   
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
    
    def create_instance(self, machine_params=dict(), wait_for_monkey_client=False):
        
        all_params = self.merge_params(self.machine_defaults, machine_params)
        all_params["zone"] = self.machine_defaults["zone"] if "zone" in self.machine_defaults else self.zones[0]
        logger.info(json.dumps(all_params, indent=2))
        try:
            source_image = all_params["source-image"]
        except:
            logger.error("""
Could not find source-image from image response.  
To use standard images, check this link https://cloud.google.com/compute/docs/images

The API documentation can be found here https://developers.google.com/resources/api-libraries/documentation/compute/v1/python/latest/compute_v1.instances.html#insert

summary below

 The source image to create this disk. When creating a new instance, one of initializeParams.sourceImage or initializeParams.sourceSnapshot or disks.source is required except for local SSD.

 To create a disk with one of the public operating system images, specify the image by its family name. For example, specify family/debian-9 to use the latest Debian 9 image:
 projects/debian-cloud/global/images/family/debian-9

 Alternatively, use a specific version of a public operating system image:
 projects/debian-cloud/global/images/debian-9-stretch-vYYYYMMDD

 To create a disk with a custom image that you created, specify the image name in the following format:
 global/images/my-custom-image

 You can also specify a custom image by its image family, which returns the latest version of the image in that family. Replace the image name with family/family-name:
 global/images/family/my-image-family
 
{}""".format(json.dumps(all_params, indent=2)))
            return None

            
        
        try:
            instance_type = all_params["instance-type"]
            instance_zone = all_params["zone"]
        except:
            logger.error("Could not find instance-type or zone in machine params\n{}".format(json.dumps(all_params, indent=2)))
            return None

        # Configure the machine
        machine_type = "zones/{}/machineTypes/{}".format(instance_zone, instance_type)

        project_zone_string = "projects/{}/zones/{}/".format(self.project, instance_zone)

        instance_name = "monkey-"
        if "name-prefix" in all_params:
            instance_name = all_params["name-prefix"]
        
        # Add random seed to end to prevent collisions
        rand_len = 6
        instance_name = instance_name + ''.join(random.choice(string.ascii_lowercase) for _ in range(rand_len))

        config = {
            'name': instance_name,
            'machineType': machine_type,

            # Specify the boot disk and the image to use as a source.
            'disks': [
                {
                    'boot': True,
                    'autoDelete': True,
                    'initializeParams': {
                        'sourceImage': 'projects/gce-uefi-images/global/images/family/ubuntu-1804-lts',
                        'diskSizeGb': all_params['disk-size'] if 'disk-size' in all_params else "10",
                        'diskType': "https://www.googleapis.com/compute/v1/{}diskTypes/{}".format(project_zone_string, all_params['disk-type'] if 'disk-type' in all_params else "pd-standard"), 
                    }
                }
            ],

            
            # Specify a network interface with NAT to access the public
            # internet.
            'networkInterfaces': [{
                'network': 'global/networks/default',
                'accessConfigs': [
                    {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
                ]
            }],

            # Allow the instance to access cloud storage and logging.
            'serviceAccounts': [{
                'email': self.credentials.service_account_email,
                'scopes': [
                    'https://www.googleapis.com/auth/devstorage.read_write',
                    'https://www.googleapis.com/auth/logging.write'
                ]
            }],
            
            # Configure network tag for monkey firewall
            'tags':{
                'items':[
                    self.firewall_rule_name
                ]
            },
            

        }

        all_labels = dict()
        if 'labels' in all_params:
            for key, value in all_params['labels'].items():
                all_labels[key] = value

        all_labels["job-creation-time"] = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Monkey Identifier (required)
        # Should be unique for every user in the providers
        if 'monkey-identifier' in all_params:
            all_labels['monkey-identifier'] = all_params['monkey-identifier']
        else:
            logger.error("You must have a the monkey-identifier set for each user in providers.yml")
            raise ValueError("You must have a the monkey-identifier set for each user in providers.yml")
            return

        # Tags the machine
        config['labels'] = all_labels

        # Preemptible setting
        if 'preemptible' in all_params:
             # Preemptible setting
            config['scheduling']= {
                'preemptible': all_params['preemptible'] if 'preemptible' in all_params else False
            }

        # GPU Configuration
        if 'gpus' in all_params:
            config['guestAccelerators'] =   [{
                'acceleratorType': "{}acceleratorTypes/{}".format(project_zone_string, all_params['gpus']['acceleratorType']),
                'acceleratorCount': all_params['gpus']['acceleratorCount']
            }]

        # Metadata
        metadata_items = []

        

        if 'metadata' in all_params:
            for key, value in all_params['metadata'].items():
                metadata_items.append({
                    'key': key,
                    'value': value
                })


        # Startup Script
        startup_script = ""
        if "startup-script-file" in all_params:
            script_file = all_params["startup-script-file"]
            try:
                startup_script = open(script_file, 'r').read()
                for metadata_set in metadata_items:
                    startup_script.replace("${}".format(metadata_set["key"]), metadata_set["value"])
                # print(startup_script)
            except:
                logger.warning("Could not read startup script file")
                raise ValueError("Could not read startup script file")
        
        # Inject beginning and end script
        start_script = None
        with open('../monkey-client/inject-start.sh') as inject_start_file:
            start_script = inject_start_file.read()
        end_script = None
        with open('../monkey-client/inject-end.sh') as inject_end_file:
            end_script = inject_end_file.read()
        if start_script is None or end_script is None:
            raise ValueError("Unable to read inject-start.sh or inject-end.sh")
        startup_script = start_script + startup_script + end_script
        metadata_items.append({
                # Startup script is automatically executed by the
                # instance upon startup.
                'key': 'startup-script',
                'value': startup_script
            })

        # Add os-login to metadata
        # metadata_items.append({
        #     'key': 'enable-oslogin',
        #     'value': 'TRUE'
        # })

        # Add project and region to env metadata items
        metadata_items.append({
            'key': 'MONKEY_PROJECT_ZONE',
            'value': project_zone_string
        })

            
        config['metadata'] = {'items': metadata_items}
        # logger.debug(json.dumps(config, indent=2))
        result = self.compute_api.instances().insert(
            project=self.project,
            zone=instance_zone,
            body=config).execute()

        operation_name = result.get('name', None)

        return_result = {
            'machine_name': instance_name,
            'machine_project': self.project,
            'machine_zone': instance_zone,
            'operation_name': operation_name,
        }
        print(return_result)
        instance = MonkeyInstanceGCP.from_creation_operation(\
                compute_api=self.compute_api, \
                machine_name=instance_name, \
                machine_zone=instance_zone, \
                machine_project=self.project, \
                operation_name=result.get('name', None))
        if wait_for_monkey_client:
            instance = instance.result()
            print("Got instance, appending in foreground")
            self.instances.append(instance)
            return instance
        self.add_instance_background(instance)
        return return_result

    @threaded
    def add_instance_background(self, instance):
        instance = instance.result()
        print("Got instance, appending in background")
        self.instances.append(instance)
        print("appending in background complete")



    def wait_for_operation(self, operation_name, timeout=40, silent=True):
        
        if not silent:
            logger.info('Waiting for operation to finish...')
        
        start = time.time()
        while time.time() - start < timeout:
            result = self.compute_api.zoneOperations().get(
                project=self.project,
                zone=self.zones[0],
                operation=operation_name).execute()
            if not silent:
                logger.debug(result)
            if result['status'] == 'DONE':
                if not silent:
                    logger.info("Operation {} done.".format(operation_name))
                if 'error' in result:
                    raise Exception(result['error'])
                return result
            time.sleep(2)

        raise TimeoutError("Waited for the operation to complete more than maximum timeout: {}".format(timeout))

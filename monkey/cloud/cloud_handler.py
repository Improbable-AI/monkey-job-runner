
import json
import time
import random
import string
import logging 
logger = logging.getLogger(__name__)

from google.oauth2 import service_account
import googleapiclient.discovery

class CloudHandler():

    credentials = None
    zones = None
    project = None
    name = None
    provider_type = None
    machine_defaults = dict()

    def merge_params(self, base, additional):
        for key, value in additional.items():
            if key in base and type(base[key]) == list:
                base[key] += value
            else:
                base[key] = value
        return base

    @staticmethod
    def create_cloud_handler(provider_info, default_params):
        provider_type = provider_info["type"]
        if provider_type == "gcp":
            return CloudHandlerGCP(provider_info, default_params)
        else:
            raise ValueError("{} type for provider not supported yet".format(provider_type))

    def __init__(self, provider_info, default_params):
        super().__init__()
        self.name = provider_info["name"]
        self.zones = provider_info["zones"]
        self.project = provider_info["project"]

        if "all" in default_params:
            self.machine_defaults = default_params["all"]

    def list_instances(self):
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
            self.zones == None or \
            self.project == None or \
            self.name == None or \
            self.provider_type == None)

    def __str__(self):
        return "Provider: {}, name: {}, zones: {}, project: {}"\
            .format(self.provider_type, self.name, ", ".join(self.zones), self.project)

class CloudHandlerGCP(CloudHandler):

    compute_api = None


    def __init__(self, provider_info, default_params):
        super().__init__(provider_info, default_params)
        self.provider_type = "gcp"
        # Overrides if type is the same
        if "gcp" in default_params:
            self.machine_defaults = self.merge_params(self.machine_defaults, default_params["gcp"])
        # Overrides if name matches
        if self.name in default_params:
            self.machine_defaults = self.merge_params(self.machine_defaults, default_params[self.name])

        logger.info("GCP Cloud Handler Instantiating {}".format(self))
        credentials_key_name = "gcp-service-key.json"
        if "credentials-key" in provider_info:
            credentials_key_name = provider_info["credentials-key"]
        self.credentials = service_account.Credentials.from_service_account_file(credentials_key_name)
        self.compute_api = googleapiclient.discovery.build('compute', 'v1', credentials=self.credentials, cache_discovery=False)
        

    def is_valid(self):
        return super().is_valid() and self.compute_api is not None
     
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
        for zone in self.zones:
            try:
                result = self.compute_api.instances().list(project=self.project, zone=zone).execute()
                result = result['items'] if 'items' in result else None
                if result:
                    instances += [inst["name"] for inst in result]
            except: 
                pass
        return instances

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
    
    def create_instance(self, machine_params):
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

            # Tags the machine
            'labels': all_params['labels'] if 'labels' in all_params else dict(),

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
                'email': 'default',
                'scopes': [
                    'https://www.googleapis.com/auth/devstorage.read_write',
                    'https://www.googleapis.com/auth/logging.write'
                ]
            }],

        }

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
        startup_script = None
        if "startup-script-file" in all_params:
            script_file = all_params["startup-script-file"]
            try:
                startup_script = open(script_file, 'r').read()
                print(metadata_items)
                for metadata_set in metadata_items:
                    startup_script.replace("${}".format(metadata_set["key"]), metadata_set["value"])
                print(startup_script)
            except:
                logger.warning("Could not read startup script file")

        if startup_script is not None:
            metadata_items.append({
                    # Startup script is automatically executed by the
                    # instance upon startup.
                    'key': 'startup-script',
                    'value': startup_script
                })
            
        config['metadata'] = {'items': metadata_items}
        logger.info(json.dumps(config, indent=2))

        return self.compute_api.instances().insert(
            project=self.project,
            zone=instance_zone,
            body=config).execute()

    def wait_for_operation(self, operation_name):
        logger.info('Waiting for operation to finish...')
        while True:
            result = self.compute_api.zoneOperations().get(
                project=self.project,
                zone=self.zones[0],
                operation=operation_name).execute()
            print(result)
            if result['status'] == 'DONE':
                logger.info("Operation {} done.".format(operation_name))
                if 'error' in result:
                    raise Exception(result['error'])
                return result

            time.sleep(1)

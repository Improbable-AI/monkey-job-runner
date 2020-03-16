

import logging 
logger = logging.getLogger(__name__)

from google.oauth2 import service_account
import googleapiclient.discovery

class CloudHandler():

    credentials = None
    zone = None
    project = None
    name = None
    provider_type = None

    @staticmethod
    def create_cloud_handler(provider_info):
        provider_type = provider_info["type"]
        

        if provider_type == "gcp":
            return CloudHandlerGCP(provider_info)
        else:
            raise ValueError("{} type for provider not supported yet".format(provider_type))

    def __init__(self, name, zone, project):
        super().__init__()
        self.name = name
        self.zone = zone
        self.project = project

    def list_instances(self):
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
        return "Provider: {}, name: {}, zone: {}, project: {}"\
            .format(self.provider_type, self.name, self.zone, self.project)

class CloudHandlerGCP(CloudHandler):

    compute_api = None


    def __init__(self, provider_info):
        provider_name = provider_info["name"]
        provider_zone = provider_info["zone"]
        provider_project = provider_info["project"]
        super().__init__(provider_name, provider_zone, provider_project)
        self.provider_type = "gcp"
        logger.info("GCP Cloud Handler Instantiating {}".format(self))
        self.credentials = service_account.Credentials.from_service_account_file('gcp-service-key.json')        
        self.compute_api = googleapiclient.discovery.build('compute', 'v1', credentials=self.credentials, cache_discovery=False)
        

    def is_valid(self):
        return super().is_valid() and self.compute_api is not None and self.check_connection()
     
    def check_connection(self):
        try:
            result = self.compute_api.instances().list(project=self.project, zone=self.zone).execute()
            result = result['items'] if 'items' in result else None
            if result:
                return True
        except: 
            pass
        return False

    def list_instances(self):
        instances = []
        try:
            result = self.compute_api.instances().list(project=self.project, zone=self.zone).execute()
            result = result['items'] if 'items' in result else None
            if result:
                return [inst["name"] for inst in result]
        except: 
            pass
        return instances
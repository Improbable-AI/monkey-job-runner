from enum import Enum
from google.oauth2 import service_account


import logging 
logger = logging.getLogger(__name__)


class CloudInstanceType(Enum):
    gcp = "GCP"
    aws = "AWS"

# A class that represenets a cloud instance.  Contains Methods that will be implemented in all
class CloudInstance():
    
    
    @staticmethod
    def get_cloud_instance(type, params):
        if type == CloudInstanceType.gcp:
            return CloudInstance.get_cloud_instance_gcp(params)
        else:
            logger.error("Cloud Instance Type Not Found")


    @staticmethod
    def get_cloud_instance_gcp(params):
        return CloudInstanceGCP(params)

    def get_type(self):
        raise NotImplementedError('This is not implemented yet')


    def get_instance_list(self):
        raise NotImplementedError('This is not implemented yet')



class CloudInstanceGCP(CloudInstance):
    
    def __init__(self, params):
        logger.info("Initialization of GCP Instance")
        credentials = service_account.Credentials.from_service_account_file('gcp-service-key.json')
        logger.info(credentials)


    def get_type(self):
        return CloudInstanceType.gcp




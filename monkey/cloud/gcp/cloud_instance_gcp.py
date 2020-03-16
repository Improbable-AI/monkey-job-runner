import monkey.cloud.cloud_instance as cloud_instance
from google.oauth2 import service_account
import logging
logger = logging.getLogger(__name__)

class CloudInstanceGCP(CloudInstance):

    def __init__(self, params):
        logger.info("Initialization of GCP Instance")
        credentials = service_account.Credentials.from_service_account_file('gcp-service-key.json')
        logger.info(credentials)



    def get_type(self):
        raise NotImplementedError('This is not implemented yet')


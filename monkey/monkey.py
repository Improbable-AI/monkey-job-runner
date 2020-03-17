import yaml, logging 
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)
logging.getLogger("google_auth_httplib2").setLevel(logging.WARNING)

from cloud.cloud_instance import CloudInstance, CloudInstanceType
from cloud.cloud_handler import CloudHandler, CloudHandlerGCP


class Monkey():

    instances = []
    handlers = []

    def __init__(self):
        super().__init__()
        logger.info("Monkey Initializing")
        self.instances = []
        self.handlers = []
        self.instantiate_handlers()
        
    def instantiate_handlers(self):
        providers = dict()
        try:
            with open("cloud_providers.yaml", 'r') as providers_file:
                providers_yaml = yaml.load(providers_file, Loader=yaml.FullLoader)
                providers = providers_yaml["providers"]
                default_params = providers_yaml["defaults"]
                # print("Found Providers {}".format(list(providers.keys())))                
        except:
            logger.error("Could not read cloud_providers.yaml for configured providers")

        if len(providers) == 0:
            logger.error("Could not find any providers in cloud_providers.yaml.  Please make sure it is filled out")
            raise ValueError("No cloud providers found")
        else:
            logger.info("Found Providers: {}".format(([p["name"] for p in providers])))

        for provider in providers:
            try:
                handler = CloudHandler.create_cloud_handler(provider_info=provider, default_params=default_params)
                if handler.is_valid():
                    self.handlers.append(handler)
                else:
                    raise ValueError("Instantiated Handler is not valid: {}".format(handler))
            except Exception as e:
                logger.error("Could not instantiate provider \n{}".format(e))


    def create_instance(self, provider, machine_params=dict()):
        logger.info("Creating Instance")
        matched_providers = [handler for handler in self.handlers if handler.name == provider]
        if len(matched_providers) != 1:
            logger.error("{} matched providers found.  Only one should have matched".format(len(matched_providers)))
            return None
        matched_provider = matched_providers[0]
        return matched_provider.create_instance(machine_params)
    
    def wait_for_operation(self, provider, operation_name):
        logger.info("Waiting for operation")
        matched_providers = [handler for handler in self.handlers if handler.name == provider]
        if len(matched_providers) != 1:
            logger.error("{} matched providers found.  Only one should have matched".format(len(matched_providers)))
            return None
        matched_provider = matched_providers[0]
        return matched_provider.wait_for_operation(operation_name)

    def get_instance_list(self):
        logger.info("Getting full instance list")
        return {handler.name : handler.list_instances() for handler in self.handlers}
    
    def get_image_list(self):
        logger.info("Getting full image list")
        return {handler.name : handler.list_images() for handler in self.handlers}
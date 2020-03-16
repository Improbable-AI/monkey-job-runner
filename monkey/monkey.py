import yaml, logging 
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)

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
                handler = CloudHandler.create_cloud_handler(provider_info=provider)
                if handler.is_valid():
                    self.handlers.append(handler)
                else:
                    raise ValueError("Instantiated Handler is not valid: {}".format(handler))
            except Exception as e:
                logger.error("Could not instantiate provider \n{}".format(e))


    def create(self):
        ins = CloudInstance.get_cloud_instance(type=CloudInstanceType.gcp, params=[])
        return "Creation Success"

    def get_instance_list(self):
        return {handler.name : handler.list_instances() for handler in self.handlers}
import yaml, logging 
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)
logging.getLogger("google_auth_httplib2").setLevel(logging.WARNING)
import threading
# from cloud.cloud_instance import CloudInstance, CloudInstanceType
from core.monkey_provider import MonkeyProvider


class Monkey():

    providers = []

    def __init__(self, providers_path="providers.yml"):
        super().__init__()
        logger.info("Monkey Initializing")
        self.providers = []
        self.instantiate_providers(providers_path=providers_path)
        
    def instantiate_providers(self, providers_path="providers.yml"):
        providers = dict()
        try:
            with open(providers_path, 'r') as providers_file:
                providers_yaml = yaml.load(providers_file, Loader=yaml.FullLoader)
                providers = providers_yaml["providers"]
        except:
            logger.error("Could not read providers.yml for configured providers")

        if len(providers) == 0:
            logger.error("Could not find any providers in providers.yml.  Please make sure it is filled out")
            raise ValueError("No providers found")
        else:
            logger.info("Found Providers: {}".format(([p["name"] for p in providers])))

        for provider in providers:
            try:
                logger.info("Try initializing: {}".format(provider))
                handler = MonkeyProvider.create_cloud_handler(provider_info=provider)
                if handler.is_valid():
                    self.providers.append(handler)
                else:
                    raise ValueError("Instantiated Handler is not valid: {}".format(handler))
            except Exception as e:
                logger.error("Could not instantiate provider \n{}".format(e))


    def submit_job(self, job_yml, foreground = True):
        print("Monkey job yml submitted:", job_yml)
        providers = job_yml.get("providers", [])
        if len(providers) == 0:
            return False, "No providers found"
        provider, provider_name = providers[0], providers[0]["name"]
        found_provider = None
        for p in self.providers:
            if p.name == provider_name:
                found_provider = p

        if found_provider is None:
            return False, "No matching provider found"

        if foreground:
            return self.run_job(provider=found_provider, job_yml=job_yml)
        else:
            t = threading.Thread(target=self.run_job, args=(found_provider, job_yml))
            t.start()
            return True, "Running in background"

    def run_job(self, provider, job_yml):
        job_uid = job_yml["job_uid"]
        created_host, creation_success = provider.create_instance(machine_params={"monkey_job_uid": job_uid})
        print("Created Host:", created_host)
        if creation_success == False:
            return False, "Failed to create and virtualize instance properly"

        # Run install scripts
        for install_item in job_yml.get("install", []):
            print("Installing item: ", install_item)
            success = created_host.install_dependency(install_item)
            if success == False:
                print("Failed to install dependency " + install_item)
                return False, "Failed to install dependency " + install_item

        success, msg = created_host.setup_job(job_yml, provider_info=provider.get_dict())
        if success == False:
            print("Failed to setup host:", msg)
            return success, msg

        success, msg = created_host.run_job(job_yml, provider_info=provider.get_dict())
        if success == False:
            print("Failed to run job:", msg)
            return success, msg
        
        return True, "Job ran successfully"


    # Fully implemented 
    def get_list_providers(self):
        return [x.get_dict() for x in self.providers]

    # Fully implemented 
    def get_list_instances(self, provider_name):
        logger.info("Getting full instance list")
        for provider in self.providers:
            if provider.name == provider_name:
                return provider.list_instances()
        return []
    
    # Unimplemented
    def get_image_list(self):
        logger.info("Getting full image list")
        return {handler.name : handler.list_images() for handler in self.providers}
import logging
import threading
from datetime import datetime, timedelta

import yaml
from termcolor import colored

import mongo.mongo_global as mongo_state
from core.monkey_provider import MonkeyProvider
from mongo.mongo_utils import get_monkey_db
from mongo.monkey_job import MonkeyJob

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)
logging.getLogger("google_auth_httplib2").setLevel(logging.WARNING)

if get_monkey_db():
    logger.info("Connected to monkeydb")
else:
    logger.info("Failed to connect to monkeydb")


class Monkey():

    lock = threading.Lock()
    providers = []

    from _monkey_list import (get_job_info, get_job_uid, get_list_instances,
                              get_list_jobs, get_list_providers)
    from _monkey_loop import (check_for_dead_jobs, check_for_queued_jobs,
                              daemon_loop, print_jobs)

    def __init__(self, providers_path="providers.yml", start_loop=True):
        super().__init__()
        logger.info("Monkey Initializing")
        self.providers = []
        self.instantiate_providers(providers_path=providers_path)
        if start_loop:
            threading.Thread(target=self.daemon_loop, daemon=True).start()

    def instantiate_providers(self, providers_path="providers.yml"):
        providers = dict()
        try:
            with open(providers_path, 'r') as providers_file:
                providers_yaml = yaml.load(providers_file,
                                           Loader=yaml.FullLoader)
                providers = providers_yaml["providers"]
        except:
            logger.error(
                "Could not read providers.yml for configured providers")

        if len(providers) == 0:
            logger.error(
                "Could not find any providers in providers.yml.  Please make sure it is filled out"
            )
            raise ValueError("No providers found")
        else:
            logger.info("Found Providers: {}".format(
                ([p["name"] for p in providers])))

        for provider in providers:
            try:
                logger.info("Try initializing: {}".format(provider["name"]))
                handler = MonkeyProvider.create_cloud_handler(
                    provider_info=provider)
                if handler.is_valid():
                    self.providers.append(handler)
                else:
                    raise ValueError(
                        "Instantiated Handler is not valid: {}".format(
                            handler))
            except Exception as e:
                logger.error("Could not instantiate provider \n{}".format(e))

    def submit_job(self, job_yml: dict, foreground=True) -> (bool, str):
        """ Persists a job to run

        Args:
            job_yml (dict): The yml that defines the job
            foreground (bool, optional): Run in foreground or let the daemond dispatch. Defaults to True.

        Returns:
            (bool, str): (Success, Message)
        """
        print("Monkey job yml submitted:")
        provider_name = job_yml["provider"]
        found_provider = None
        for p in self.providers:
            if p.name == provider_name:
                found_provider = p

        if found_provider is None:
            return False, "No matching provider found"

        job_random_suffix = job_yml["job_uid"].split("-")[-1]
        # Add job to monkeydb
        job = MonkeyJob(job_uid=job_yml["job_uid"],
                        job_random_suffix=job_random_suffix,
                        job_yml=job_yml,
                        state=mongo_state.MONKEY_STATE_QUEUED,
                        provider_name=provider_name,
                        provider_type=found_provider.provider_type,
                        provider_vars=found_provider.get_dict())
        job.save()

        if foreground:
            job.set_state(state=mongo_state.MONKEY_STATE_DISPATCHING)
            return self.run_job(provider=found_provider, job_yml=job_yml)
        else:
            return True, "Running in background"

    def run_job(self, provider, job_yml):
        """ Runs a job in the monkey core system

        Args:
            provider (MonkeyProvider): The MonkeyProvider object that will execute the job
            job_yml (dict): Full job yml

        Returns:
            (bool, str): (Success, Message)
        """
        job_uid = job_yml["job_uid"]
        dbMonkeyJob = MonkeyJob.objects(job_uid=job_uid).get()
        logger.info(dbMonkeyJob)
        logger.info("Dispatching:".format(job_uid))
        machine_params = dict()
        for provider_yml in job_yml["providers"]:
            if provider_yml.get("name", "") == provider.name:
                for key, val in provider_yml.items():
                    machine_params[key] = val
                break
        machine_params["monkey_job_uid"] = job_uid

        dbMonkeyJob.set_state(
            state=mongo_state.MONKEY_STATE_DISPATCHING_MACHINE)
        created_host, creation_success = provider.create_instance(
            machine_params=machine_params)
        logger.info("Created Host:".format(created_host))
        if creation_success == False:
            print("Failed to create and virtualize instance properly")
            dbMonkeyJob.set_state(state=mongo_state.MONKEY_STATE_QUEUED)
            return False, "Failed to create and virtualize instance properly"
        logger.info("{}: Successfully dispatched machine".format(job_uid))

        dbMonkeyJob.set_state(
            state=mongo_state.MONKEY_STATE_DISPATCHING_INSTALLS)
        # Run install scripts
        for install_item in job_yml.get("install", []):
            print("Installing item: ", install_item)
            success = created_host.install_dependency(install_item)
            if success == False:
                print("Failed to install dependency " + install_item)
                dbMonkeyJob.set_state(state=mongo_state.MONKEY_STATE_QUEUED)
                return False, "Failed to install dependency " + install_item

        logger.info(
            "{}: Successfully configured machine installs".format(job_uid))

        dbMonkeyJob.set_state(state=mongo_state.MONKEY_STATE_DISPATCHING_SETUP)
        success, msg = created_host.setup_job(
            job_yml, provider_info=provider.get_dict())
        if success == False:
            print("Failed to setup host:", msg)
            dbMonkeyJob.set_state(state=mongo_state.MONKEY_STATE_QUEUED)
            return success, msg
        logger.info("{}: Successfully configured host environment: {}".format(
            job_uid, msg))

        dbMonkeyJob.set_state(state=mongo_state.MONKEY_STATE_RUNNING)
        success, msg = created_host.run_job(job_yml,
                                            provider_info=provider.get_dict())
        if success == False:
            print("Failed to run job:", msg)
            dbMonkeyJob.set_state(state=mongo_state.MONKEY_STATE_QUEUED)
            return success, msg
        dbMonkeyJob.total_wall_time = (
            datetime.now() - dbMonkeyJob.creation_date).total_seconds()
        dbMonkeyJob.set_state(state=mongo_state.MONKEY_STATE_CLEANUP)
        success, msg = created_host.cleanup_job(
            job_yml, provider_info=provider.get_dict())
        if success == False:
            print("Job ran correctly, but cleanup failed:", msg)
            return success, msg
        dbMonkeyJob.set_state(state=mongo_state.MONKEY_STATE_FINISHED)
        return True, "Job ran successfully"

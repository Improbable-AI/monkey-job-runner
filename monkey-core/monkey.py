import yaml, logging 
import threading
from datetime import datetime, timedelta
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)
logging.getLogger("google_auth_httplib2").setLevel(logging.WARNING)
import threading
# from cloud.cloud_instance import CloudInstance, CloudInstanceType
from core.monkey_provider import MonkeyProvider
from setup.mongo_utils import *
from termcolor import colored

DAEMON_THREAD_TIME = 15
if get_monkey_db():
    logger.info("Connected to monkeydb")
else:
    logger.info("Failed to connect to monkeydb")

class Monkey():

    lock = threading.Lock()
    providers = []

    def __init__(self, providers_path="providers.yml"):
        super().__init__()
        logger.info("Monkey Initializing")
        self.providers = []
        self.instantiate_providers(providers_path=providers_path)
        threading.Thread(target=self.daemon_loop).start()
    
    def daemon_loop(self):
        threading.Timer(DAEMON_THREAD_TIME, self.daemon_loop).start()
        with self.lock:
            print(colored("\n======================================================================", "blue"))
            logger.info(" :{}:Running periodic check".format(datetime.now()))
            self.check_for_queued_jobs()
            self.check_for_dead_jobs()

    def check_for_queued_jobs(self):
        """Checks for all queued jobs and dispatches if necessary
        """
        queued_jobs = MonkeyJob.objects(state=MONKEY_STATE_QUEUED)
        print("Found", len(queued_jobs), "queued jobs")
        for job in queued_jobs:
            print("Dispatching Job: ", job.job_uid)
            found_provider = None
            for p in self.providers:
                if p.name == job.provider_name:
                    found_provider = p
            assert found_provider, "Provider should have been defined for the job to be submitted"
            job.set_state(state=MONKEY_STATE_DISPATCHING)
            threading.Thread(target=self.run_job, args=(found_provider, job.job_yml)).start()
    
    def check_for_dead_jobs(self):
        pending_jobs = MonkeyJob.objects(creation_date__gte=(datetime.now() - timedelta(days=10)))
        pending_job_num = len([x for x in pending_jobs if x.state != MONKEY_STATE_FINISHED and x.state != MONKEY_STATE_CLEANUP])
        potential_missed_cleanup_num = len(pending_jobs) - pending_job_num
        print("Found: {} jobs in pending state".format(pending_job_num))
        print("Checking: {} jobs for late cleanup".format(potential_missed_cleanup_num))


        def print_job_state(job, elapsed_time=None, timeout=None ):
            elapsed_time = elapsed_time if elapsed_time is not None else ""
            timeout = timeout if timeout is not None else ""
            print("job_uid: {}, state: {}, elapsed: {}, timeout: {}".format(job.job_uid, job.state, elapsed_time, timeout ))

        # TODO: retry counts
        for job in pending_jobs:
            if job.state == MONKEY_STATE_QUEUED:
                continue
            found_provider = None
            for p in self.providers:
                if p.name == job.provider_name:
                    found_provider = p
            if found_provider is None:
                logger.error("Provider should have been defined for the job to be submitted: {}".format(job))

            job.total_wall_time = (datetime.now() - job.creation_date).total_seconds()
            if job.state == MONKEY_STATE_DISPATCHING_MACHINE:
                time_elapsed = (datetime.now() - job.run_dispatch_machine_start_date).total_seconds()
                print_job_state(job, elapsed_time=time_elapsed, timeout=MONKEY_TIMEOUT_DISPATCHING_MACHINE)
                if time_elapsed > MONKEY_TIMEOUT_DISPATCHING_MACHINE:
                    print("Found DISPATCHING_MACHINE with time: ", time_elapsed, "\n\nRESETTING TO QUEUED\n\n")
                    job.set_state(state=MONKEY_STATE_QUEUED)
            elif job.state == MONKEY_STATE_DISPATCHING_INSTALLS:
                time_elapsed = (datetime.now() - job.run_dispatch_installs_start_date).total_seconds()
                print_job_state(job, elapsed_time=time_elapsed, timeout=MONKEY_TIMEOUT_DISPATCHING_INSTALLS)
                if time_elapsed > MONKEY_TIMEOUT_DISPATCHING_INSTALLS:
                    print("Found DISPATCHING_INSTALLS with time: ", time_elapsed, "\n\nRESETTING TO QUEUED\n\n")
                    job.set_state(state=MONKEY_STATE_QUEUED)
            elif job.state == MONKEY_STATE_DISPATCHING_SETUP:
                time_elapsed = (datetime.now() - job.run_dispatch_setup_start_date).total_seconds()
                print_job_state(job, elapsed_time=time_elapsed, timeout=MONKEY_TIMEOUT_DISPATCHING_SETUP)
                if time_elapsed > MONKEY_TIMEOUT_DISPATCHING_SETUP:
                    print("Found DISPATCHING_SETUP with time: ", time_elapsed, "\n\nRESETTING TO QUEUED\n\n")
                    job.set_state(state=MONKEY_STATE_QUEUED)
            elif job.state == MONKEY_STATE_RUNNING:
                time_elapsed = (datetime.now() - job.run_running_start_date).total_seconds()
                print_job_state(job, elapsed_time=time_elapsed, timeout=job.run_timeout_time)
                if (job.run_timeout_time != -1 and job.run_timeout_time != 0) \
                    and time_elapsed > job.run_timeout_time:
                    logger.info("Reached maximum running time: {}.  Killing job".format(job.job_uid))
                    # Will run until finished cleanup 
                    job.set_state(state=MONKEY_STATE_FINISHED)
            elif job.state == MONKEY_STATE_CLEANUP:
                time_elapsed = (datetime.now() - job.run_cleanup_start_date).total_seconds()
                print_job_state(job, elapsed_time=time_elapsed, timeout=MONKEY_TIMEOUT_CLEANUP)
                instance = found_provider.get_instance(job.job_uid)
                if instance is None:
                    print("Skipping cleanup, machine already destroyed")
                    job.set_state(MONKEY_STATE_FINISHED)
                elif time_elapsed > MONKEY_TIMEOUT_CLEANUP:
                    print("RESTARTING CLEANUP\n\nCLEANUP TIMEOUT TRIGGERED\n\n")
                    threading.Thread(target=instance.cleanup_job, args=(job.job_yml, found_provider.get_dict())).start()
                    job.run_cleanup_start_date = datetime.now()
                    job.save()
            elif job.state == MONKEY_STATE_FINISHED:
                # Check if there are finished jobs that haven't been cleaned
                instance = found_provider.get_instance(job.job_uid)
                if instance is not None:
                    print("Found inished machine with existing instance.  \n\nCLEANUP STATE SET\n\n")
                    job.set_state(MONKEY_STATE_CLEANUP)
                    threading.Thread(target=instance.cleanup_job, args=(job.job_yml, found_provider.get_dict())).start()
                    


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
        """ Persists a job to run

        Args:
            job_yml (dict): The yml that defines the job
            foreground (bool, optional): Run in foreground or let the daemond dispatch. Defaults to True.

        Returns:
            (bool, str): (Success, Message)
        """
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

        # Add job to monkeydb
        job = MonkeyJob(job_uid=job_yml["job_uid"],
                        job_yml=job_yml,
                        state=MONKEY_STATE_QUEUED,
                        provider_name=provider_name,
                        provider_type=found_provider.provider_type,
                        provider_vars=found_provider.get_dict())
        job.save()

        if foreground:
            job.set_state(state=MONKEY_STATE_DISPATCHING)
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
        if dbMonkeyJob.state.startswith(MONKEY_STATE_DISPATCHING):
            print("Monkey Job {} is already in a dispatching state".format(dbMonkeyJob))
        logger.info("Dispatching:".format(job_uid))
        dbMonkeyJob.set_state(state=MONKEY_STATE_DISPATCHING_MACHINE)
        created_host, creation_success = provider.create_instance(machine_params={"monkey_job_uid": job_uid})
        logger.info("Created Host:".format(created_host))
        if creation_success == False:
            return False, "Failed to create and virtualize instance properly"
        logger.info("{}: Successfully dispatched machine".format(job_uid))

        dbMonkeyJob.set_state(state=MONKEY_STATE_DISPATCHING_INSTALLS)
        # Run install scripts
        for install_item in job_yml.get("install", []):
            print("Installing item: ", install_item)
            success = created_host.install_dependency(install_item)
            if success == False:
                print("Failed to install dependency " + install_item)
                return False, "Failed to install dependency " + install_item

        logger.info("{}: Successfully configured machine installs".format(job_uid))

        dbMonkeyJob.set_state(state=MONKEY_STATE_DISPATCHING_SETUP)
        success, msg = created_host.setup_job(job_yml, provider_info=provider.get_dict())
        if success == False:
            print("Failed to setup host:", msg)
            return success, msg
        logger.info("{}: Successfully configured host environment: {}".format(job_uid, msg))

        dbMonkeyJob.set_state(state=MONKEY_STATE_RUNNING)
        success, msg = created_host.run_job(job_yml, provider_info=provider.get_dict())
        if success == False:
            print("Failed to run job:", msg)
            return success, msg
        dbMonkeyJob.run_elapsed_time += (datetime.now() - dbMonkeyJob.run_running_start_date).total_seconds()
        dbMonkeyJob.total_wall_time = (datetime.now() - dbMonkeyJob.creation_date).total_seconds()
        dbMonkeyJob.set_state(state=MONKEY_STATE_CLEANUP)
        success, msg = created_host.cleanup_job(job_yml, provider_info=provider.get_dict())
        if success == False:
            print("Job ran correctly, but cleanup failed:", msg)
            return success, msg 
        dbMonkeyJob.set_state(state=MONKEY_STATE_FINISHED)
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
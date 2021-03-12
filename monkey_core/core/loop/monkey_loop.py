import logging
import threading
from datetime import datetime, timedelta

from core import monkey_global
from core.mongo import mongo_global as monkey_state
from core.mongo.monkey_job import MonkeyJob
from termcolor import colored

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


def check_for_queued_jobs(self, log_file=None):
    """Checks for all queued jobs and dispatches if necessary
    """
    queued_jobs = MonkeyJob.objects(state=monkey_state.MONKEY_STATE_QUEUED)
    printout = f"Found {len(queued_jobs)}  queued jobs\n"

    for job in queued_jobs:
        printout += f"Dispatching Job: {job.job_uid}\n"
        found_provider = None
        for p in self.providers:
            if p.name == job.provider_name:
                found_provider = p
        if found_provider is None:
            printout += "Provider should have been defined for the job to be submitted\n"
            continue
        job.set_state(state=monkey_state.MONKEY_STATE_DISPATCHING)
        threading.Thread(target=self.run_job,
                         args=(found_provider, job.job_yml),
                         daemon=True).start()

    if not monkey_global.QUIET_PERIODIC_PRINTOUT:
        print(printout)
    if log_file:
        log_file.write(printout)


def print_jobs_string(self, jobs):
    printout = ""
    header = colored("{:^26} {:^24} {:^19} {:^13} ".format("Job Name", "State",
                                                           "Elapsed(s)", "Timeout(s)"),
                     attrs=["bold"])
    printout += f"\n{header}\n"
    for job in jobs:
        timeout = monkey_state.state_to_timeout(
            job.state) if monkey_state.state_to_timeout(job.state) is not None else ""
        line = colored("{:^26} {:^24} {:^19.1f} {:^13} ".format(
            job.job_uid, job.state, job.time_elapsed_in_state(), timeout))
        printout += f"{line}\n"
    printout += "\n"
    return printout


def check_for_dead_jobs(self, log_file=None):
    pending_jobs = MonkeyJob.objects(creation_date__gte=(datetime.now() -
                                                         timedelta(days=10)))

    current_jobs = [
        x for x in pending_jobs if x.state != monkey_state.MONKEY_STATE_FINISHED
        and x.state != monkey_state.MONKEY_STATE_CLEANUP
    ]

    pending_job_num = len(current_jobs)
    cleanup_jobs = [
        x for x in pending_jobs if x.state == monkey_state.MONKEY_STATE_CLEANUP
    ]
    potential_missed_cleanup_num = len(cleanup_jobs)

    printout = f"Found: {pending_job_num} jobs in pending state\n"
    printout += f"Checking: {potential_missed_cleanup_num} jobs for late cleanup\n"
    printout += self.print_jobs_string(
        [x for x in pending_jobs if x.state != monkey_state.MONKEY_STATE_FINISHED])

    if not monkey_global.QUIET_PERIODIC_PRINTOUT:
        print(printout)

    if log_file:
        log_file.write(printout)

    # TODO (averylamp): retry counts
    for job in pending_jobs:
        if job.state == monkey_state.MONKEY_STATE_QUEUED:
            continue
        found_provider = None
        for p in self.providers:
            if p.name == job.provider_name:
                found_provider = p
        if found_provider is None:
            logger.error(
                "Provider should have been defined for the job to be submitted: {}"
                .format(job))
            continue

        job.total_wall_time = (datetime.now() - job.creation_date).total_seconds()

        timeout_for_state = monkey_state.state_to_timeout(job.state)
        time_elapsed = job.time_elapsed_in_state()
        if timeout_for_state is not None and time_elapsed > timeout_for_state and job.state != monkey_state.MONKEY_STATE_CLEANUP:
            print("Found Timed out job with state {}.  Requeueing job".format(job.state))
            job.set_state(monkey_state.MONKEY_STATE_QUEUED)
        if job.provider_type == "local":
            print("looking for local instance: ", job.job_yml["instance"])
            instance = found_provider.get_instance(job.job_yml["instance"])
        else:
            instance = found_provider.get_instance(job.job_uid)

        if (job.state not in [
                monkey_state.MONKEY_STATE_QUEUED, monkey_state.MONKEY_STATE_FINISHED,
                monkey_state.MONKEY_STATE_DISPATCHING_MACHINE,
                monkey_state.MONKEY_STATE_DISPATCHING, monkey_state.MONKEY_STATE_CLEANUP
        ]):
            # Instance can't be found and should have been created already
            if (instance is None
                    and job.state != monkey_state.MONKEY_STATE_DISPATCHING_MACHINE):

                job.set_state(monkey_state.MONKEY_STATE_QUEUED)
            # Instance found and is offline
            elif (instance is not None and not instance.check_online()):
                job.set_state(monkey_state.MONKEY_STATE_QUEUED)

        if job.state == monkey_state.MONKEY_STATE_RUNNING:
            if (job.run_timeout_time != -1 and job.run_timeout_time != 0) \
                and time_elapsed > job.run_timeout_time:
                logger.info("Reached maximum running time: {}.  Killing job".format(
                    job.job_uid))
                # Will run until finished cleanup
                job.set_state(state=monkey_state.MONKEY_STATE_CLEANUP)
        elif job.state == monkey_state.MONKEY_STATE_CLEANUP:
            instance = found_provider.get_instance(job.job_uid)
            if instance is None:
                print("Skipping cleanup, machine already destroyed")
                job.set_state(monkey_state.MONKEY_STATE_FINISHED)

            if (job.run_cleanup_start_date is None) or (
                ((time_elapsed > monkey_state.MONKEY_TIMEOUT_CLEANUP) and
                 (instance is not None and instance.check_online() == True))):
                threading.Thread(target=instance.cleanup_job,
                                 args=(job.job_yml, found_provider.get_dict())).start()
                job.run_cleanup_start_date = datetime.now()
            elif (instance is not None and instance.check_online() == False):
                job.set_state(monkey_state.MONKEY_STATE_FINISHED)
        elif job.state == monkey_state.MONKEY_STATE_FINISHED:
            # Check if there are finished jobs that haven't been cleaned
            instance = found_provider.get_instance(job.job_uid)
            if instance is not None and instance.check_online() == True:
                print("Machine found existing in finished state, cleaning...")
                job.set_state(monkey_state.MONKEY_STATE_CLEANUP)
        job.save()


def check_for_job_hyperparameters(self, log_file=None):
    jobs_without_hyperparameters = MonkeyJob.objects(experiment_hyperparameters=dict())
    jobs_without_hyperparameters_num = len(jobs_without_hyperparameters)

    printout = f"Found: {jobs_without_hyperparameters_num} jobs without parameters\n"
    if not monkey_global.QUIET_PERIODIC_PRINTOUT:
        print(printout)
    if log_file:
        log_file.write(printout)

    for job in jobs_without_hyperparameters:
        if job.state not in (monkey_state.MONKEY_STATE_RUNNING,
                             monkey_state.MONKEY_STATE_CLEANUP,
                             monkey_state.MONKEY_STATE_FINISHED):
            continue
        found_provider = None
        for p in self.providers:
            if p.name == job.provider_name:
                found_provider = p
        if found_provider is None:
            logger.error(
                "Provider should have been defined for the job to be submitted: {}"
                .format(job))
            continue
        instance = found_provider.get_instance(job.job_uid)
        if instance is not None:
            hyperparameters = instance.get_experiment_hyperparameters()
            if hyperparameters is not None:
                job.experiment_hyperparameters = hyperparameters
                job.save()
                print("Found hyperparameters for job {}: {}".format(
                    job.job_uid, hyperparameters))
            else:
                print("No hyperparameters for job {}".format(job.job_uid))


def daemon_loop(self):  #
    threading.Timer(monkey_global.DAEMON_THREAD_TIME, self.daemon_loop).start()
    with self.lock:
        with open(monkey_global.STATUS_LOG_FILE, "w") as f:
            printout = colored(
                "\n======================================================================\n",
                "blue")
            printout += f"{datetime.now()}: Running Periodic Check \n"
            if not monkey_global.QUIET_PERIODIC_PRINTOUT:
                print(printout)
            f.write(printout)
            self.check_for_queued_jobs(f)
            self.check_for_dead_jobs(f)
            self.check_for_job_hyperparameters(f)

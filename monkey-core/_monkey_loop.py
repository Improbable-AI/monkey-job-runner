import logging
import threading
from datetime import datetime, timedelta

from termcolor import colored

from setup.mongo_utils import *

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
DAEMON_THREAD_TIME = 5


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
        threading.Thread(target=self.run_job,
                         args=(found_provider, job.job_yml)).start()


def check_for_dead_jobs(self):
    pending_jobs = MonkeyJob.objects(creation_date__gte=(datetime.now() -
                                                         timedelta(days=10)))

    current_jobs = [
        x for x in pending_jobs
        if x.state != MONKEY_STATE_FINISHED and x.state != MONKEY_STATE_CLEANUP
    ]

    pending_job_num = len(current_jobs)
    cleanup_jobs = [x for x in pending_jobs if x.state == MONKEY_STATE_CLEANUP]
    potential_missed_cleanup_num = len(cleanup_jobs)
    recently_finished_jos = [
        x for x in pending_jobs if x.state == MONKEY_STATE_FINISHED
    ]
    print("Found: {} jobs in pending state".format(pending_job_num))
    print("Checking: {} jobs for late cleanup".format(
        potential_missed_cleanup_num))

    def print_job_state(job, elapsed_time=None, timeout=None):
        elapsed_time = elapsed_time if elapsed_time is not None else ""
        timeout = timeout if timeout is not None else ""
        print("job_uid: {}, state: {}, elapsed: {}, timeout: {}".format(
            job.job_uid, job.state, elapsed_time, timeout))

    # TODO (averylamp): retry counts
    for job in pending_jobs:
        if job.state == MONKEY_STATE_QUEUED:
            continue
        found_provider = None
        for p in self.providers:
            if p.name == job.provider_name:
                found_provider = p
        if found_provider is None:
            logger.error(
                "Provider should have been defined for the job to be submitted: {}"
                .format(job))

        job.total_wall_time = (datetime.now() -
                               job.creation_date).total_seconds()
        if job.state == MONKEY_STATE_DISPATCHING_MACHINE:
            time_elapsed = (
                datetime.now() -
                job.run_dispatch_machine_start_date).total_seconds()
            print_job_state(job,
                            elapsed_time=time_elapsed,
                            timeout=MONKEY_TIMEOUT_DISPATCHING_MACHINE)
            if time_elapsed > MONKEY_TIMEOUT_DISPATCHING_MACHINE:
                print("Found DISPATCHING_MACHINE with time: ", time_elapsed,
                      "\n\nRESETTING TO QUEUED\n\n")
                job.set_state(state=MONKEY_STATE_QUEUED)
        elif job.state == MONKEY_STATE_DISPATCHING_INSTALLS:
            time_elapsed = (
                datetime.now() -
                job.run_dispatch_installs_start_date).total_seconds()
            print_job_state(job,
                            elapsed_time=time_elapsed,
                            timeout=MONKEY_TIMEOUT_DISPATCHING_INSTALLS)
            if time_elapsed > MONKEY_TIMEOUT_DISPATCHING_INSTALLS:
                print("Found DISPATCHING_INSTALLS with time: ", time_elapsed,
                      "\n\nRESETTING TO QUEUED\n\n")
                job.set_state(state=MONKEY_STATE_QUEUED)
        elif job.state == MONKEY_STATE_DISPATCHING_SETUP:
            time_elapsed = (datetime.now() -
                            job.run_dispatch_setup_start_date).total_seconds()
            print_job_state(job,
                            elapsed_time=time_elapsed,
                            timeout=MONKEY_TIMEOUT_DISPATCHING_SETUP)
            if time_elapsed > MONKEY_TIMEOUT_DISPATCHING_SETUP:
                print("Found DISPATCHING_SETUP with time: ", time_elapsed,
                      "\n\nRESETTING TO QUEUED\n\n")
                job.set_state(state=MONKEY_STATE_QUEUED)
        elif job.state == MONKEY_STATE_RUNNING:
            time_elapsed = (datetime.now() -
                            job.run_running_start_date).total_seconds()
            print_job_state(job,
                            elapsed_time=time_elapsed,
                            timeout=job.run_timeout_time)
            if (job.run_timeout_time != -1 and job.run_timeout_time != 0) \
                and time_elapsed > job.run_timeout_time:
                logger.info(
                    "Reached maximum running time: {}.  Killing job".format(
                        job.job_uid))
                # Will run until finished cleanup
                job.set_state(state=MONKEY_STATE_FINISHED)
        elif job.state == MONKEY_STATE_CLEANUP:
            time_elapsed = (datetime.now() -
                            job.run_cleanup_start_date).total_seconds()
            print_job_state(job,
                            elapsed_time=time_elapsed,
                            timeout=MONKEY_TIMEOUT_CLEANUP)
            instance = found_provider.get_instance(job.job_uid)
            if instance is None:
                print("Skipping cleanup, machine already destroyed")
                job.set_state(MONKEY_STATE_FINISHED)
            elif time_elapsed > MONKEY_TIMEOUT_CLEANUP:
                print("RESTARTING CLEANUP\n\nCLEANUP TIMEOUT TRIGGERED\n\n")
                threading.Thread(target=instance.cleanup_job,
                                 args=(job.job_yml,
                                       found_provider.get_dict())).start()
                job.run_cleanup_start_date = datetime.now()
                job.save()
        elif job.state == MONKEY_STATE_FINISHED:
            # Check if there are finished jobs that haven't been cleaned
            instance = found_provider.get_instance(job.job_uid)
            if instance is not None:
                print(
                    "Found inished machine with existing instance.  \n\nCLEANUP STATE SET\n\n"
                )
                job.set_state(MONKEY_STATE_CLEANUP)
                threading.Thread(target=instance.cleanup_job,
                                 args=(job.job_yml,
                                       found_provider.get_dict())).start()


def daemon_loop(self):  #
    threading.Timer(DAEMON_THREAD_TIME, self.daemon_loop).start()
    with self.lock:
        print(
            colored(
                "\n======================================================================",
                "blue"))
        print("{}:Running periodic check".format(datetime.now()))
        self.check_for_queued_jobs()
        self.check_for_dead_jobs()

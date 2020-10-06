import logging
import threading
from datetime import datetime, timedelta

from termcolor import colored

import mongo.mongo_global as state
from mongo.monkey_job import MonkeyJob

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
DAEMON_THREAD_TIME = 5


def check_for_queued_jobs(self):
    """Checks for all queued jobs and dispatches if necessary
    """
    queued_jobs = MonkeyJob.objects(state=state.MONKEY_STATE_QUEUED)
    print("Found", len(queued_jobs), "queued jobs")
    for job in queued_jobs:
        print("Dispatching Job: ", job.job_uid)
        found_provider = None
        for p in self.providers:
            if p.name == job.provider_name:
                found_provider = p
        if found_provider is None:
            print(
                "Provider should have been defined for the job to be submitted"
            )
            continue
        job.set_state(state=state.MONKEY_STATE_DISPATCHING)
        threading.Thread(target=self.run_job,
                         args=(found_provider, job.job_yml)).start()


def print_jobs(self, jobs):
    header = colored("{:^26} {:^24} {:^11} {:^11} ".format(
        "Job Name", "State", "Elapsed(s)", "Timeout(s)"),
                     attrs=["bold"])
    print("")
    print(header)
    print("")
    for job in jobs:
        timeout = state.state_to_timeout(job.state) if state.state_to_timeout(
            job.state) is not None else ""
        line = colored("{:^26} {:^24} {:^19.1f} {:^13} ".format(
            job.job_uid, job.state, job.time_elapsed_in_state(), timeout))
        print(line)
    print("")


def check_for_dead_jobs(self):
    pending_jobs = MonkeyJob.objects(creation_date__gte=(datetime.now() -
                                                         timedelta(days=10)))

    current_jobs = [
        x for x in pending_jobs if x.state != state.MONKEY_STATE_FINISHED
        and x.state != state.MONKEY_STATE_CLEANUP
    ]

    pending_job_num = len(current_jobs)
    cleanup_jobs = [
        x for x in pending_jobs if x.state == state.MONKEY_STATE_CLEANUP
    ]
    potential_missed_cleanup_num = len(cleanup_jobs)
    recently_finished_jos = [
        x for x in pending_jobs if x.state == state.MONKEY_STATE_FINISHED
    ]
    print("Found: {} jobs in pending state".format(pending_job_num))
    print("Checking: {} jobs for late cleanup".format(
        potential_missed_cleanup_num))

    self.print_jobs(
        [x for x in pending_jobs if x.state != state.MONKEY_STATE_FINISHED])

    # TODO (averylamp): retry counts
    for job in pending_jobs:
        if job.state == state.MONKEY_STATE_QUEUED:
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

        timeout_for_state = state.state_to_timeout(job.state)
        time_elapsed = job.time_elapsed_in_state()
        if timeout_for_state is not None and time_elapsed > timeout_for_state:
            print("Found Timed out job with state {}.  Requeueing job".format(
                job.state))
            job.set_state(state.MONKEY_STATE_QUEUED)

        if job.state == state.MONKEY_STATE_RUNNING:
            if (job.run_timeout_time != -1 and job.run_timeout_time != 0) \
                and time_elapsed > job.run_timeout_time:
                logger.info(
                    "Reached maximum running time: {}.  Killing job".format(
                        job.job_uid))
                # Will run until finished cleanup
                job.set_state(state=state.MONKEY_STATE_CLEANUP)
        elif job.state == state.MONKEY_STATE_CLEANUP:
            instance = found_provider.get_instance(job.job_uid)
            if instance is None:
                print("Skipping cleanup, machine already destroyed")
                job.set_state(state.MONKEY_STATE_FINISHED)
            elif time_elapsed > state.MONKEY_TIMEOUT_CLEANUP:
                print("RESTARTING CLEANUP\n\nCLEANUP TIMEOUT TRIGGERED\n\n")
                threading.Thread(target=instance.cleanup_job,
                                 args=(job.job_yml,
                                       found_provider.get_dict())).start()
                job.run_cleanup_start_date = datetime.now()
        elif job.state == state.MONKEY_STATE_FINISHED:
            # Check if there are finished jobs that haven't been cleaned
            instance = found_provider.get_instance(job.job_uid)
            if instance is not None:
                print(
                    "Found finished machine with existing instance.  \n\nCLEANUP STATE SET\n\n"
                )
                job.set_state(state.MONKEY_STATE_CLEANUP)
                threading.Thread(target=instance.cleanup_job,
                                 args=(job.job_yml,
                                       found_provider.get_dict())).start()
        job.save()


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

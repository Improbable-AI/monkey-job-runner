import logging

logger = logging.getLogger(__name__)
from mongo import *


def get_job_uid(self, uid):
    jobs = MonkeyJob.objects(job_uid=uid).order_by("-creation_date")
    if len(jobs) > 0:
        return jobs[0].job_uid
    jobs = MonkeyJob.objects(job_random_suffix=uid).order_by("-creation_date")
    if len(jobs) > 0:
        return jobs[0].job_uid
    return None


def get_job_config(self, uid):
    jobs = MonkeyJob.objects(job_uid=uid).order_by("-creation_date")
    if len(jobs) == 0:
        return None
    job = jobs[0]
    return job.experiment_hyperparameters


def get_job_info(self, uid):
    print(f"Getting job info for uid {uid}")
    jobs = MonkeyJob.objects(job_uid=uid).order_by("-creation_date")
    print(f"Monkey objects found {len(jobs)}")

    print(jobs)
    if len(jobs) == 0:
        None
    job = jobs[0]
    return job.get_dict()


def get_list_providers(self):
    return [x.get_dict() for x in self.providers]


def get_list_local_instances(self):
    local_instances = []
    for provider in self.providers:
        if provider.provider_type == "local":
            local_instances += provider.get_local_instances_list()
    return local_instances


def get_list_jobs(self, options=dict()):
    # logger.info("Getting full job list")
    try:
        num_jobs = int(options.get("num_jobs", -1))
    except:
        pass

    if num_jobs is not None and num_jobs != -1:
        jobs = [
            x.get_dict() for x in MonkeyJob.objects().order_by(
                "-creation_date").limit(num_jobs)
        ]
    else:
        jobs = [x.get_dict() for x in MonkeyJob.objects()]
    return jobs


# Fully implemented
def get_list_instances(self, provider_name):
    # logger.info("Getting instance list for: {}".format(provider_name))
    for provider in self.providers:
        if provider.name == provider_name:
            return provider.list_instances()
    return []


# Unimplemented
def get_image_list(self):
    logger.info("Getting full image list")
    return {handler.name: handler.list_images() for handler in self.providers}

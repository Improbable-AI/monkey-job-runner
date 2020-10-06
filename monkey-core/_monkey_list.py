import logging

logger = logging.getLogger(__name__)
from mongo import *


# Fully implemented
def get_list_providers(self):
    return [x.get_dict() for x in self.providers]


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

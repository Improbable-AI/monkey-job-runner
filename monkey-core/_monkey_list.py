import logging

logger = logging.getLogger(__name__)
from setup.mongo_utils import *


# Fully implemented
def get_list_providers(self):
    return [x.get_dict() for x in self.providers]


def get_list_jobs(self, options=dict()):
    logger.info("Getting full job list")
    jobs = MonkeyJob.objects()
    return jobs


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
    return {handler.name: handler.list_images() for handler in self.providers}

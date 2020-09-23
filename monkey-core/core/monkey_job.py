import datetime
import json
import logging
import random
import string
import time

logger = logging.getLogger(__name__)


class MonkeyJob():
    job_name = None


class MonkeyJobGCP(MonkeyJob):
    def __init__(self, ):
        super().__init__()

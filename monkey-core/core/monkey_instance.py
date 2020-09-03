
import ansible_runner
from concurrent.futures import Future
from threading import Thread
import json
import time
import random
import string
import datetime
import threading
import requests
import yaml
import os
import logging
logger = logging.getLogger(__name__)

HEARTBEAT_TIME = 30
HEARTBEAT_FAILURE_TOLERANCE = 3


# Creates backgound decorators @threaded.  To block and get the result, use .result()
def call_with_future(fn, future, args, kwargs):
    try:
        result = fn(*args, **kwargs)
        future.set_result(result)
    except Exception as exc:
        future.set_exception(exc)


def threaded(fn):
    def wrapper(*args, **kwargs):
        future = Future()
        Thread(target=call_with_future, args=(
            fn, future, args, kwargs)).start()
        return future
    return wrapper


class MonkeyInstance():

    name = None
    machine_zone = None
    machine_project = None
    creation_time = None
    destruction_time = None
    ip_address = None
    state = None

    def __init__(self, name, machine_zone, machine_project, ip_address):
        super().__init__()
        self.name = name
        self.machine_zone = machine_zone
        self.machine_project = machine_project
        self.ip_address = ip_address

        threading.Thread(target=self.heartbeat_loop, daemon=True)

    def heartbeat_loop(self):
        while True:
            time.sleep(HEARTBEAT_TIME)
            r = requests.get("http://{}:9991/ping".format(self.ip_address))

    def install_dependency(self, dependency):
        raise NotImplementedError("This is not implemented yet")

    def setup_job(self, job, provider_info=dict()):
        raise NotImplementedError("This is not implemented yet")

    def run_job(self, job, provider_info=dict()):
        raise NotImplementedError("This is not implemented yet")

    def cleanup_job(self, job, provider_info=dict()):
        raise NotImplementedError("This is not implemented yet")

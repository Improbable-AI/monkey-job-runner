import logging
import threading
import uuid
from concurrent.futures import Future
from datetime import datetime
from threading import Thread

import requests

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
        Thread(target=call_with_future,
               args=(fn, future, args, kwargs)).start()
        return future

    return wrapper


class MonkeyInstance():

    name = None
    machine_zone = None
    creation_time = None
    destruction_time = None
    ip_address = None
    state = None
    lock = threading.Lock()

    offline_count = 0
    offline_retries = 3
    last_uuid = None

    def __init__(self, name, machine_zone, ip_address):
        super().__init__()
        self.name = name
        self.machine_zone = machine_zone
        self.ip_address = ip_address
        self.creation_time = datetime.now()
        # threading.Thread(target=self.heartbeat_loop, daemon=True)

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        return self.creation_time < other.creation_time

    def check_online(self):
        if self.ip_address is None:
            return False
        try:
            r = requests.get("http://{}:9991/ping".format(self.ip_address),
                             timeout=4)
        except:
            self.offline_count += 1
            return self.offline_count >= self.offline_retries
        if not r.ok:
            self.offline_count += 1
        if self.offline_count >= self.offline_retries:
            return False
        self.offline_count = 0
        return True

    def update_instance_details(self, other):
        self.name = other.name
        self.machine_zone = other.machine_zone
        self.ip_address = other.ip_address

    def get_uuid(self):
        with self.lock:
            uuid = self.last_uuid
        return uuid

    def update_uuid(self):
        with self.lock:
            new_uuid = uuid.uuid1()
            print("\n\nUpdating uuid\nfrom: {}\nto  :{}\n\n".format(
                self.last_uuid, new_uuid))
            self.last_uuid = new_uuid
        return new_uuid

    def ansible_runner_uuid_cancel(self, uuid):
        def check_for_uuid_change():
            change = self.last_uuid != uuid
            # print("Checking uuid: {} != {}, : {}".format(
            # self.last_uuid, uuid, change))
            return change

        return check_for_uuid_change

    def check_uuid(self, uuid):
        check = False
        with self.lock:
            if self.last_uuid == uuid:
                check = True
        return check

    def install_dependency(self, dependency):
        raise NotImplementedError("This is not implemented yet")

    def setup_job(self, job, provider_info=dict()):
        raise NotImplementedError("This is not implemented yet")

    def run_job(self, job, provider_info=dict()):
        raise NotImplementedError("This is not implemented yet")

    def cleanup_job(self, job, provider_info=dict()):
        raise NotImplementedError("This is not implemented yet")

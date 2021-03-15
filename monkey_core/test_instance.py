import threading
import time

from core import monkey_global
from core.mongo.monkey_job import MonkeyJob
from core.monkey import Monkey

# monkey_global.QUIET_ANSIBLE = True
monkey = Monkey(start_loop=False)

print("Starting test_instance")
aws_provider = monkey.providers[0]
print(aws_provider)
print(aws_provider.list_instances())
instance = list(aws_provider.instances.values())[0]
print(instance)

job = MonkeyJob.objects()[0]
job_yml = job.job_yml
print(job_yml)

print(instance.get_json())
print(instance.ansible_info)
instance.setup_dependency_manager(job_uid=instance.get_json()["name"],
                                  run_yml=job_yml["run"])

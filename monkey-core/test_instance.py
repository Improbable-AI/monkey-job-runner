import threading
import time

import monkey_global
from mongo.monkey_job import MonkeyJob
from monkey import Monkey

monkey_global.QUIET_ANSIBLE = True
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


def run(run_number):
    time.sleep(5)
    print("Starting install.....")
    for install_item in job_yml.get("install", []):
        print("Installing item: ", install_item)
        success = instance.install_dependency(install_item)
        if success == False:
            print("\n\nFAILED: {}\n\n".format(run_number))
            return

    success, msg = instance.setup_job(job_yml, provider_info=aws_provider.get_dict())
    if success == False:
        print("Failed to setup host:", msg)
        print("\n\nFAILED: {}\n\n".format(run_number))
        return success, msg

    success, msg = instance.run_job(job_yml, provider_info=aws_provider.get_dict())
    if success == False:
        print("Failed to run job:", msg)
        print("\n\nFAILED: {}\n\n".format(run_number))
        return success, msg

    success, msg = instance.cleanup_job(job_yml, provider_info=aws_provider.get_dict())
    if success == False:
        print("Job ran correctly, but cleanup failed:", msg)
        print("\n\nFAILED: {}\n\n".format(run_number))
        return success, msg


tr = threading.Thread(target=run, args=(1,))

tr.start()

time.sleep(10)

print("\n\n\n\n\nStarting second run\n\n\n\n")

tr2 = threading.Thread(target=run, args=(2,))

tr2.start()

tr.join()

tr2.join()

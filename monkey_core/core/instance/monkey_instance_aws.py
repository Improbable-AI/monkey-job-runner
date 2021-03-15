import logging
import os

import ansible_runner
from core import monkey_global
from core.instance.monkey_instance import AnsibleRunException, MonkeyInstance
from core.setup_scripts.utils import aws_cred_file_environment, get_aws_vars

logger = logging.getLogger(__name__)


class MonkeyInstanceAWS(MonkeyInstance):
    ansible_info = None

    def __str__(self):
        return """Monkey AWS Instance
name: {}, ip: {}, state: {}
        """.format(self.ip_address, self.name, self.state)

    def get_json(self):
        return {
            "name": self.name,
            "ip_address": self.ip_address,
            "state": self.state,
            "machine_zone": self.machine_zone,
        }

    def get_monkeyfs_dir(self):
        return "/monkeyfs"

    def get_scratch_dir(self):
        return "/home/ubuntu"

    def get_job_dir(self, job_uid):
        return "/home/ubuntu"

    # Passes compute_api in order to restart instances
    def __init__(self, ansible_info):

        name = ansible_info["tags"]["Name"]
        self.job_uid = ansible_info["tags"]["Name"]
        self.machine_zone = ansible_info["placement"]["availability_zone"]

        try:
            self.ip_address = ansible_info["network_interfaces"][0][
                "association"]["public_ip"]
        except:
            self.ip_address = None

        super().__init__(name=name, ip_address=self.ip_address)
        self.ansible_info = ansible_info
        self.state = ansible_info["state"]["name"]

    def update_instance_details(self, other):
        super().update_instance_details(other)
        self.ansible_info = other.ansible_info
        self.state = other.state
        self.machine_zone = other.machine_zone

    def check_online(self):

        return super().check_online() and self.state == "running"

    def install_dependency(self, dependency):
        logger.info(f"Instance installing: {dependency}")

        try:
            self.run_ansible_role(rolename=f"install/{dependency}")
        except AnsibleRunException as e:
            print(e)
            logger.error(f"Installing Dependency: {dependency} failed")
            return False

        logger.info(f"Installing Dependency: {dependency} succeeded!")
        return True

    def mount_monkeyfs(self, job_yml, provider_info):
        credential_file = provider_info.get("aws_cred_file", None)
        aws_storage_name = provider_info["storage_name"]
        monkeyfs_path = provider_info.get("monkeyfs_path", "/monkeyfs")
        if credential_file is None:
            return False, "Service account credential file is not provided"

        print("Mounting filesystem...")
        cred_environment = aws_cred_file_environment(credential_file)

        setup_job_args = {
            "aws_storage_name": aws_storage_name,
            "monkeyfs_path": monkeyfs_path,
            "access_key_id": cred_environment["AWS_ACCESS_KEY_ID"],
            "access_key_secret": cred_environment["AWS_SECRET_ACCESS_KEY"]
        }
        try:
            self.run_ansible_role(
                rolename="aws/mount_fs",
                extravars=setup_job_args,
            )
        except AnsibleRunException as e:
            print(e)
            print("Failed to mount filesystem")
            return False, "Failed to mount monkeyfs filesystem"
        return True, "Mounted Monkeyfs properly"

    def cleanup_job(self, job_yml, provider_info={}):
        job_uid = job_yml["job_uid"]
        print("\n\nTerminating Machine:", job_uid, "\n\n")
        # Cleanup skipped for now
        print(provider_info)

        delete_instance_params = {
            "monkey_job_uid": job_uid,
            "aws_zone": provider_info["zone"],
            "aws_region": provider_info["zone"],
        }

        for key, val in get_aws_vars().items():
            delete_instance_params[key] = val

        uuid = self.update_uuid()
        runner = ansible_runner.run(
            host_pattern="localhost",
            private_data_dir="ansible",
            module="include_role",
            module_args="name=aws/delete",
            extravars=delete_instance_params,
            quiet=monkey_global.QUIET_ANSIBLE,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))

        if self.get_uuid() != uuid:
            print("Failed Deletion of machine")
            return False, "Failed to cleanup job after completion, cancelled due to concurrency"
        if runner.status == "failed":
            print("Failed Deletion of machine")
            return False, "Failed to cleanup job after completion"
        return True, "Succesfully cleaned up job"

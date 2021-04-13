import logging

import ansible_runner
from core import monkey_global
from core.instance.monkey_instance import AnsibleRunException, MonkeyInstance
from core.setup_scripts.utils import get_gcp_vars

logger = logging.getLogger(__name__)


class MonkeyInstanceGCP(MonkeyInstance):

    ansible_info = None

    def __str__(self):
        return """Monkey GCP Instance
name: {}, ip: {}, state: {}
        """.format(self.ip_address, self.name, self.state)

    def get_json(self):
        return {
            "name": self.name,
            "ip_address": self.ip_address,
            "state": self.state,
            "machine_zone": self.machine_zone,
            "machine_project": self.machine_project,
        }

    def get_monkeyfs_dir(self):
        return "/monkeyfs"

    def get_scratch_dir(self):
        return f"/home/{self.gcp_user}"

    def get_job_dir(self, job_uid):
        return f"/home/{self.gcp_user}"

    def __init__(self, ansible_info, gcp_user):
        self.name = ansible_info["name"]
        self.machine_zone = ansible_info["zone"]
        self.machine_project = ansible_info["project"]
        self.gcp_user = gcp_user

        # Look for public IP
        network_interfaces = ansible_info.get("networkInterfaces", [])
        access_configs = next(iter(network_interfaces),
                              dict()).get("accessConfigs", [])
        self.ip_address = next(iter(access_configs), dict()).get("natIP", None)

        super().__init__(name=self.name, ip_address=self.ip_address)
        self.ansible_info = ansible_info
        self.state = ansible_info["status"]

    def mount_monkeyfs(self, job_yml, provider_info):
        gcp_storage_name = provider_info["gcp_storage_name"]
        monkeyfs_path = provider_info.get("monkeyfs_path", "/monkeyfs")

        logger.debug("Mounting filesystem...")

        setup_job_args = {
            "gcp_storage_name": gcp_storage_name,
            "monkeyfs_path": monkeyfs_path,
            "ansible_user": self.gcp_user
        }
        try:
            self.run_ansible_role(
                rolename="gcp/mount_fs",
                extravars=setup_job_args,
            )
        except AnsibleRunException as e:
            logger.error(e)
            logger.error("Failed to mount filesystem")
            return False, "Failed to mount monkeyfs filesystem"
        return True, "Mounted Monkeyfs properly"

    def cleanup_job(self, job_yml, provider_info={}):
        job_uid = job_yml["job_uid"]
        logger.debug("\n\nTerminating Machine:", job_uid, "\n\n")
        # Cleanup skipped for now

        delete_instance_params = {
            "monkey_job_uid": job_uid,
        }

        for key, val in get_gcp_vars().items():
            delete_instance_params[key] = val

        uuid = self.update_uuid()
        runner = ansible_runner.run(
            host_pattern="localhost",
            private_data_dir="ansible",
            module="include_role",
            module_args="name=gcp/delete",
            extravars=delete_instance_params,
            quiet=monkey_global.QUIET_ANSIBLE,
            cancel_callback=self.ansible_runner_uuid_cancel(uuid))

        if self.get_uuid() != uuid:
            logger.error("Failed Deletion of machine")
            return False, "Failed to cleanup job after completion, cancelled due to concurrency"
        if runner.status == "failed":
            logger.error("Failed Deletion of machine")
            return False, "Failed to cleanup job after completion"
        return True, "Succesfully cleaned up job"

import os

from core.instance.monkey_instance import AnsibleRunException


#############################################
#
#  1. Set up the dataset by unpacking it
#
#############################################
def setup_data_item(self, data_item, job_uid):
    installation_location = os.path.join(self.get_job_dir(), data_item["path"])

    dataset_full_path = self.get_dataset_path(data_name=data_item["name"],
                                              checksum=data_item["checksum"],
                                              extension=data_item["extension"])
    print("Copying dataset from", dataset_full_path, " to ", installation_location)

    try:
        self.run_ansible_module(modulename="file",
                                args={
                                    "path": installation_location,
                                    "state": "directory"
                                })

        self.run_ansible_module(modulename="unarchive",
                                args={
                                    "src": dataset_full_path,
                                    "remote_src": "True",
                                    "dest": installation_location,
                                })
    except AnsibleRunExcpetion as e:
        print(e)
        return False, "Failed to extract archive"

    print("Successfully setup data item")
    return True, "Successfully setup data item"


#############################################
#
#  2. Unpack Job Dir
#
#############################################
def unpack_job_dir(self, job_uid, monkeyfs_path, job_dir_path):
    job_path = os.path.join(monkeyfs_path, "jobs", job_uid)

    uuid = self.update_uuid()
    runner = self.run_ansible_module(
        modulename="copy",
        args=f"src={job_path + '/' } dest={job_dir_path} remote_src=true",
        uuid=uuid)
    if runner.status == "failed" or self.get_uuid() != uuid:
        print("Failed to copy directory")
        return False, "Failed to copy directory"

    print("Unpacked job dir successfully")
    return True, "Unpacked code and persisted directories successfully"


#############################################
#
#  3. Unpack codebase
#
#############################################
def unpack_code_and_persist(self, code_item, monkeyfs_path, job_dir_path):
    print(code_item)
    run_name = code_item["run_name"]
    checksum = code_item["codebase_checksum"]
    extension = code_item["codebase_extension"]
    code_tar_path = os.path.join(monkeyfs_path, "code", run_name, checksum,
                                 "code" + extension)

    uuid = self.update_uuid()
    print("Code tar path: ", code_tar_path)
    print("Run dir: ", job_dir_path)
    job_dir_path = os.path.join(job_dir_path, "")
    runner = self.run_ansible_module(modulename="unarchive",
                                     args={
                                         "src": code_tar_path,
                                         "remote_src": "True",
                                         "dest": job_dir_path,
                                         "creates": "yes"
                                     },
                                     uuid=uuid)
    if runner.status == "failed" or self.get_uuid() != uuid:
        print("Failed to unpack code")
        return False, "Failed to extract code archive"

    print("Unpacked code successfully")
    return True, "Unpacked code and persisted directories successfully"


def setup_logs_folder(self, monkeyfs_path, job_uid, job_dir_path):
    print("Persisting logs: ")
    logs_path = os.path.join(job_dir_path, "logs", "")
    monkeyfs_output_folder = \
        os.path.join(monkeyfs_path, "jobs", job_uid, "logs", "")
    sync_logs_path = os.path.join(job_dir_path, "logs", "sync.log")
    script_path = os.path.join(job_dir_path, ".logs_sync.sh")
    sync_folder_path = os.path.join(job_dir_path, "sync")
    uuid = self.update_uuid()
    persist_folder_args = {
        "persist_folder_path": logs_path,
        "sync_logs_path": sync_logs_path,
        "sync_folder_path": sync_folder_path,
        "persist_script_path": script_path,
        "bucket_path": monkeyfs_output_folder,
        "persist_time": 3,
    }
    runner = self.run_ansible_role(rolename="local/configure/persist_folder",
                                   extravars=persist_folder_args,
                                   uuid=uuid)

    if runner.status == "failed" or self.get_uuid() != uuid:
        print("Failed to create persisted logs folder")
        return False, "Failed to create persisted logs folder"

    return True, "Setup logs persistence ran successfully"


def setup_persist_folder(self, job_uid, monkeyfs_path, job_dir_path, persist):
    print("Persisting folder: ", persist)
    persist_path = persist
    persist_name = persist.replace("/", "_") + "_sync.sh"
    sync_folder_path = os.path.join(job_dir_path, "sync")
    script_path = os.path.join(job_dir_path, "sync", persist_name)
    sync_logs_path = os.path.join(job_dir_path, "logs", "sync.log")
    monkeyfs_output_folder = \
        os.path.join(monkeyfs_path, "jobs", job_uid, persist_path, "")
    persist_folder_path = os.path.join(job_dir_path, persist_path, "")

    print("Output folder: ", monkeyfs_output_folder)
    print("Input folder: ", persist_folder_path)

    uuid = self.update_uuid()
    persist_folder_args = {
        "persist_folder_path": persist_folder_path,
        "sync_folder_path": sync_folder_path,
        "sync_logs_path": sync_logs_path,
        "persist_script_path": script_path,
        "bucket_path": monkeyfs_output_folder,
    }
    runner = self.run_ansible_role(rolename="local/configure/persist_folder",
                                   extravars=persist_folder_args,
                                   uuid=uuid)

    if runner.status == "failed" or self.get_uuid() != uuid:
        print("Failed to setup persist folder: " + persist_path)
        return False, f"Failed to setup persist folder: {persist_path}"
    return True, "Setup persist ran successfully"


def start_persist(self, job_uid, monkeyfs_path, job_dir_path):
    print("Starting Persist")
    unique_persist_all_script_name = job_uid + "_" + "persist_all_loop.sh"
    sync_folder_path = os.path.join(job_dir_path, "sync")
    script_path = os.path.join(job_dir_path, "sync", "persist_all.sh")
    sync_logs_path = os.path.join(job_dir_path, "logs", "sync.log")
    script_loop_path = os.path.join(job_dir_path, "sync", unique_persist_all_script_name)

    uuid = self.update_uuid()
    start_persist_args = {
        "sync_folder_path": sync_folder_path,
        "sync_logs_path": sync_logs_path,
        "persist_script_path": script_path,
        "unique_persist_all_script_name": unique_persist_all_script_name,
        "persist_loop_script_path": script_loop_path,
    }
    runner = self.run_ansible_role(rolename="local/configure/start_persist",
                                   extravars=start_persist_args,
                                   uuid=uuid)

    if runner.status == "failed" or self.get_uuid() != uuid:
        print("Runner status: ", runner.status)
        print("UUID: ", self.get_uuid(), ", other: ", uuid)
        print("Failed start persistence of directories")
        return False, "Failed start persistence of directories"
    return True, "Start persist ran successfully"


def setup_dependency_manager(self, run_yml, job_dir_path):
    env_type = run_yml["env_type"]
    env_file = run_yml["env_file"]
    env_file = os.path.join(job_dir_path, env_file)
    print("Env type: ", env_type)
    print("Env file: ", env_file)
    activate_file = os.path.join(job_dir_path, ".monkey_activate")
    uuid = self.update_uuid()
    env_args = {
        "environment_file": env_file,
        "activate_file": activate_file,
        "job_dir_path": job_dir_path
    }
    if env_type == "conda":
        runner = self.run_ansible_role(rolename="run/local/setup_conda",
                                       extravars=env_args,
                                       uuid=uuid)
    elif env_type == "pip":
        runner = self.run_ansible_role(rolename="run/local/setup_pip",
                                       extravars=env_args,
                                       uuid=uuid)
    elif env_type == "docker":
        runner = self.run_ansible_role(rolename="run/local/setup_docker",
                                       extravars=env_args,
                                       uuid=uuid)
    else:
        return False, "Provided or missing dependency manager"

    if runner.status == "failed" or self.get_uuid() != uuid:
        return False, "Failed to initialize environment manager"

    return True, "Successfully created dependency manager and stored initialization in .monkey_activate"

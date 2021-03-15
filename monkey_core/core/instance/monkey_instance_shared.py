import os

from core.instance.monkey_instance import AnsibleRunException


#############################################
#
#  1. Set up the dataset by unpacking it
#
#############################################
def setup_data_item(self, job_uid, data_item):
    installation_location = os.path.join(self.get_job_dir(job_uid=job_uid),
                                         data_item["path"])

    dataset_full_path = self.get_dataset_path(data_name=data_item["name"],
                                              checksum=data_item["checksum"],
                                              extension=data_item["extension"])
    print("Copying dataset from", dataset_full_path, " to ",
          installation_location)

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
    except AnsibleRunException as e:
        print(e)
        return False, "Failed to extract archive"

    print("Successfully setup data item")
    return True, "Successfully setup data item"


#############################################
#
#  2. Unpack Job Dir
#
#############################################
def unpack_job_dir(self, job_uid):
    job_path = os.path.join(self.get_job_dir(job_uid=job_uid), "")
    monkeyfs_job_path = os.path.join(
        self.get_monkeyfs_job_dir(job_uid=job_uid), "")

    try:
        self.run_ansible_module(modulename="copy",
                                args={
                                    "src": monkeyfs_job_path,
                                    "dest": job_path,
                                    "remote_src": True
                                })
    except AnsibleRunException as e:
        print(e)
        print("Failed to copy directory")
        return False, "Failed to copy directory"

    print("Unpacked job dir successfully")
    return True, "Unpacked code and persisted directories successfully"


#############################################
#
#  3. Unpack codebase
#
#############################################
def unpack_code_and_persist(self, job_uid, code_item):
    print(code_item)
    run_name = code_item["run_name"]
    checksum = code_item["checksum"]
    extension = code_item["extension"]

    code_tar_path = self.get_codebase_file_path(run_name=run_name,
                                                checksum=checksum,
                                                extension=extension)

    job_dir_path = self.get_job_dir(job_uid=job_uid)
    print("Code tar path: ", code_tar_path)
    print("Run dir: ", job_dir_path)

    try:
        self.run_ansible_module(modulename="unarchive",
                                args={
                                    "src": code_tar_path,
                                    "remote_src": "True",
                                    "dest": job_dir_path,
                                    "creates": "yes"
                                })
    except AnsibleRunException as e:
        print(e)
        print("Failed to unpack code")
        return False, "Failed to extract code archive"

    print("Unpacked code successfully")
    return True, "Unpacked code and persisted directories successfully"


#############################################
#
#  4. Sets up Logs folder
#
#############################################
def setup_logs_folder(self, job_uid):
    """
    Creates a logs folder and a sync script which will get executed
    Every time persist_all is executed
    """
    print("Persisting logs: ")
    job_dir_path = self.get_job_dir(job_uid=job_uid)
    logs_path = os.path.join(job_dir_path, "logs", "")
    monkeyfs_job_dir = self.get_monkeyfs_job_dir(job_uid=job_uid)
    monkeyfs_output_folder = os.path.join(monkeyfs_job_dir, "logs", "")

    sync_logs_path = os.path.join(job_dir_path, "logs", "sync.log")
    script_path = os.path.join(job_dir_path, "logs_sync.sh")
    sync_folder_path = os.path.join(job_dir_path, "sync")
    persist_folder_args = {
        "persist_folder_path": logs_path,
        "sync_logs_path": sync_logs_path,
        "sync_folder_path": sync_folder_path,
        "persist_script_path": script_path,
        "bucket_path": monkeyfs_output_folder,
        "persist_time": 3,
    }
    try:
        self.run_ansible_role(
            rolename="local/configure/persist_folder",
            extravars=persist_folder_args,
        )
    except AnsibleRunException as e:
        print(e)
        print("Failed to create persisted logs folder")
        return False, "Failed to create persisted logs folder"

    return True, "Setup logs persistence ran successfully"


#############################################
#
#  5. Set up Persist folders
#
#############################################
def setup_persist_folder(self, job_uid, persist):
    """
    For every folder defined, a persist script is generated.
    The persist script will live in {job_dir}/sync/ and be executed
    periodically at shutdown or upon completion
    """
    print("Persisting folder: ", persist)
    job_dir_path = self.get_job_dir(job_uid=job_uid)
    persist_path = persist
    persist_name = persist.replace("/", "_") + "_sync.sh"
    sync_folder_path = os.path.join(job_dir_path, "sync")
    script_path = os.path.join(job_dir_path, "sync", persist_name)
    sync_logs_path = os.path.join(job_dir_path, "logs", "sync.log")
    monkeyfs_output_folder = \
        os.path.join(self.get_monkeyfs_job_dir(job_uid=job_uid), persist_path, "")
    persist_folder_path = os.path.join(job_dir_path, persist_path, "")

    print("Output folder: ", monkeyfs_output_folder)
    print("Input folder: ", persist_folder_path)

    persist_folder_args = {
        "persist_folder_path": persist_folder_path,
        "sync_folder_path": sync_folder_path,
        "sync_logs_path": sync_logs_path,
        "persist_script_path": script_path,
        "bucket_path": monkeyfs_output_folder,
    }
    try:
        self.run_ansible_role(rolename="local/configure/persist_folder",
                              extravars=persist_folder_args)
    except AnsibleRunException as e:
        print(e)
        print("Failed to setup persist folder: " + persist_path)
        return False, f"Failed to setup persist folder: {persist_path}"
    return True, "Setup persist ran successfully"


#############################################
#
#  6. Starts Persist Script Loop
#
#############################################
def start_persist(self, job_uid):
    """
    The persist script loop runs every designated time period
    and will sync all persisted folders, logs, or other defined persists
    The persist script loop is uniquely named to allow for killing by name
    """
    job_dir_path = self.get_job_dir(job_uid=job_uid)
    unique_persist_all_script_name = job_uid + "_" + "persist_all_loop.sh"
    sync_folder_path = os.path.join(job_dir_path, "sync")
    script_path = os.path.join(job_dir_path, "sync", "persist_all.sh")
    sync_logs_path = os.path.join(job_dir_path, "logs", "sync.log")
    script_loop_path = os.path.join(job_dir_path, "sync",
                                    unique_persist_all_script_name)

    start_persist_args = {
        "sync_folder_path": sync_folder_path,
        "sync_logs_path": sync_logs_path,
        "persist_script_path": script_path,
        "unique_persist_all_script_name": unique_persist_all_script_name,
        "persist_loop_script_path": script_loop_path,
    }
    try:
        self.run_ansible_role(rolename="local/configure/start_persist",
                              extravars=start_persist_args)
    except AnsibleRunException as e:
        print(e)
        print("Failed start persistence of directories")
        return False, "Failed start persistence of directories"

    return True, "Start persist ran successfully"


#############################################
#
#  7. Setup Environment Activation
#
#############################################
def setup_dependency_manager(self, job_uid, run_yml):
    """
    For every environment type, there needs to be special activation code
    added to the .monkey_activate to load environment variables upon run script.
    """
    job_dir_path = self.get_job_dir(job_uid=job_uid)
    env_type = run_yml["env_type"]
    env_file = run_yml["env_file"]
    env_file = os.path.join(job_dir_path, env_file)
    print("Env type: ", env_type)
    print("Env file: ", env_file)
    activate_file = os.path.join(job_dir_path, ".monkey_activate")
    env_args = {
        "environment_file": env_file,
        "activate_file": activate_file,
        "job_dir_path": job_dir_path
    }
    try:
        if env_type == "conda":
            self.run_ansible_role(rolename="run/local/setup_conda",
                                  extravars=env_args)
        elif env_type == "pip":
            self.run_ansible_role(rolename="run/local/setup_pip",
                                  extravars=env_args)
        elif env_type == "docker":
            self.run_ansible_role(rolename="run/local/setup_docker",
                                  extravars=env_args)
        else:
            return False, "Provided or missing dependency manager"

    except AnsibleRunException as e:
        print(e)
        return False, "Failed to initialize environment manager"

    return True, "Successfully created dependency manager" + \
        "\nStored initialization in .monkey_activate"


#############################################
#
#  8. Run Command
#
#############################################
def execute_command(self, job_uid, cmd, run_yml):
    """
    This helper function will activate the .monkey_activate
    and run the defined command while piping output to the logs folder
    """
    print("Executing cmd: ", cmd)
    print("Environment Variables:", run_yml.get("env", dict()))

    job_dir_path = self.get_job_dir(job_uid=job_uid)
    activate_file = self.get_monkey_activate_file(job_uid=job_uid)

    try:
        self.run_ansible_role(
            rolename="run/local/cmd",
            extravars={
                "run_command": cmd,
                "job_dir_path": job_dir_path,
                "activate_file": activate_file,
            },
            envvars=run_yml.get("env", dict()),
        )

    except Exception as e:
        print(e)
        return False, "Failed to run command properly: " + cmd

    return True, "Successfully ran job"


def run_job(self, job_yml, provider_info=dict()):
    """
    This function will run the job after setup and sync all persisted
    folders upon job completion
    """
    print("Running job: ", job_yml)
    job_uid = job_yml["job_uid"]
    success, msg = self.execute_command(job_uid=job_uid,
                                        cmd=job_yml["cmd"],
                                        run_yml=job_yml["run"])
    if not success:
        return success, msg

    print("\n\nRan job:", job_uid, " SUCCESSFULLY!\n\n")

    sync_all_script_path = self.get_persist_all_script(job_uid=job_uid)
    try:
        self.run_ansible_shell(command=f"bash {sync_all_script_path}",)
    except Exception as e:
        print(e)
        return False, "Failed to run sync command properly: "
    print("Ended syncing")
    return True, "Ran job successfully"

import copy
import logging
import os
import random
import string
import tarfile
import tempfile
import threading
from datetime import datetime

import yaml from core import monkey_global from core.routes.utils import (existing_dir, get_codebase_path,
                               get_dataset_file_path, get_dataset_path,
                               get_local_filesystem_for_provider,
                               sync_directories)
from flask import Blueprint, jsonify, request, send_file
from ruamel.yaml import YAML, round_trip_load
from werkzeug.datastructures import FileStorage

dispatch_routes = Blueprint("dispatch_routes", __name__)

logger = logging.getLogger(__name__)

date_format = "monkey-%y-%m-%d-"
instance_number = 0
last_date = datetime.now().strftime(date_format)

lock = threading.Lock()

UNIQUE_UIDS = True


@dispatch_routes.route('/get/new_job_uid')
def get_new_job_uid():
    with lock:
        global date_format, instance_number, last_date
        new_date = datetime.now().strftime(date_format)
        if new_date != last_date:

            last_date = new_date
            instance_number = 1
        else:
            logger.info(f"Would be instance {last_date + str(instance_number + 1)}")
            pass
            instance_number += 1
        if UNIQUE_UIDS == True:
            return last_date + str(instance_number) + "-" + ''.join(
                random.choice(string.ascii_lowercase) for _ in range(3))
    return last_date + str(instance_number)


def check_checksum_path(local_path, provider_path, directory, name, checksum):

    def get_checksum_path(base_path):
        abs_path = os.path.abspath(os.path.join(base_path, directory, name, checksum))
        return abs_path, existing_dir(abs_path)

    local_path, local_found = get_checksum_path(base_path=local_path)
    provider_path, provider_found = get_checksum_path(base_path=provider_path)

    logger.info(
        f"local: {local_path}, provider path: {provider_path}, local_found: {local_found}, provider_found: {provider_found}"
    )

    if local_found and not provider_found:
        sync_directories(local_path, provider_path)

    return jsonify({
        "msg":
            f"Found existing {directory}"
            if local_found else f"Need to upload {directory}...",
        "found":
            local_found,
    })


@dispatch_routes.route('/check/dataset')
def check_dataset():
    dataset_name = request.args.get('name', None)
    dataset_checksum = request.args.get('checksum', None)
    logger.info(f"Checking dataset: {dataset_name}:{dataset_checksum}")
    provider = request.args.get('provider', None)

    if dataset_name is None or dataset_checksum is None or provider is None:
        return jsonify({
            "msg": "Did not provide name or checksum or provider",
            "found": False
        })

    monkeyfs_path = get_local_filesystem_for_provider(provider)

    return check_checksum_path(local_path=monkey_global.MONKEYFS_LOCAL_PATH,
                               provider_path=monkeyfs_path,
                               directory="data",
                               name=dataset_name,
                               checksum=dataset_checksum)


@dispatch_routes.route('/upload/dataset', methods=["POST"])
def upload_dataset():
    logger.info("Received upload dataset request")
    dataset_name = request.args.get('name', None)
    dataset_checksum = request.args.get('checksum', None)
    dataset_path = request.args.get('path', None)
    dataset_extension = request.args.get('extension', None)
    provider = request.args.get('provider', None)
    dataset_yaml = {
        "name": dataset_name,
        "checksum": dataset_checksum,
        "path": dataset_path,
        "extension": dataset_extension,
    }
    logger.info(dataset_yaml)
    if dataset_name is None or dataset_checksum is None or dataset_path is None \
            or dataset_extension is None or provider is None:
        return jsonify({
            "msg":
                "Did not provide name or checksum or path or extension or provider, for dataset upload",
            "success":
                False
        })
    monkeyfs_path = get_local_filesystem_for_provider(provider)
    local_path = get_dataset_path(dataset_name=dataset_name,
                                  dataset_checksum=dataset_checksum,
                                  monkeyfs_path=monkey_global.MONKEYFS_LOCAL_PATH)

    provider_path = get_dataset_path(dataset_name=dataset_name,
                                     dataset_checksum=dataset_checksum,
                                     monkeyfs_path=monkeyfs_path)

    doc_yaml_path = os.path.join(local_path, "dataset.yaml")
    os.makedirs(local_path, exist_ok=True)

    local_dataset_file_path = get_dataset_file_path(
        dataset_name=dataset_name,
        dataset_checksum=dataset_checksum,
        dataset_extension=dataset_extension,
        monkeyfs_path=monkey_global.MONKEYFS_LOCAL_PATH)
    FileStorage(request.stream).save(local_dataset_file_path)
    logger.info("Saved file to: {}".format(
        os.path.join(local_path, "data" + dataset_extension)))
    with open(doc_yaml_path, "w") as doc_yaml_file:
        yaml.dump(dataset_yaml, doc_yaml_file)
    sync_directories(local_path, provider_path)
    return jsonify({"msg": "Successfully uploaded dataset", "success": True})


@dispatch_routes.route('/check/codebase')
def check_codebase():
    run_name = request.args.get('run_name', None)
    codebase_checksum = request.args.get('checksum', None)
    logger.info("Checking codebase: {}:{}".format(run_name, codebase_checksum))
    provider = request.args.get('provider', None)

    if run_name is None or codebase_checksum is None or provider is None:
        return jsonify({
            "msg": "Did not provide run_name or checksum or provider",
            "found": False
        })

    monkeyfs_path = get_local_filesystem_for_provider(provider)
    return check_checksum_path(local_path=monkey_global.MONKEYFS_LOCAL_PATH,
                               provider_path=monkeyfs_path,
                               directory="code",
                               name=run_name,
                               checksum=codebase_checksum)


@dispatch_routes.route('/upload/codebase', methods=["POST"])
def upload_codebase():
    job_uid = request.args.get('job_uid', None)
    provider = request.args.get('provider', None)
    run_name = request.args.get('run_name', None)
    checksum = request.args.get('checksum', None)
    already_uploaded = request.args.get("already_uploaded", False)
    codebase_extension = request.args.get('extension', None)

    logger.info(f"Already uploaded: {already_uploaded is not None}")
    if already_uploaded is not None:
        try:
            if type(already_uploaded) is str:
                if already_uploaded.lower() == "false":
                    already_uploaded = False
                elif already_uploaded.lower() == "true":
                    already_uploaded = True
                else:
                    already_uploaded = False
        except Exception:
            already_uploaded = False

    codebase_yaml = {
        "run_name": run_name,
        "checksum": checksum,
        "provider": provider,
        "extension": codebase_extension
    }

    logger.info(f"Received upload codebase request: {job_uid}")
    if job_uid is None or provider is None:
        return jsonify({"msg": "Did not provide job_uid or provider", "success": False})
    monkeyfs_path = get_local_filesystem_for_provider(provider)

    job_folder_path = os.path.join(monkey_global.MONKEYFS_LOCAL_PATH, "jobs", job_uid)
    provider_job_folder_path = os.path.join(monkeyfs_path, "jobs", job_uid)
    os.makedirs(os.path.join(job_folder_path, "logs"), exist_ok=True)
    os.makedirs(os.path.join(provider_job_folder_path, "logs"), exist_ok=True)
    if not os.path.exists(os.path.join(job_folder_path, "logs", "run.log")):
        with open(os.path.join(job_folder_path, "logs", "run.log"), "a") as f:
            f.write("Initializing machines...")
    if not os.path.exists(os.path.join(provider_job_folder_path, "logs", "run.log")):
        with open(os.path.join(job_folder_path, "logs", "run.log"), "a") as f:
            f.write("Initializing machines...")
    logger.info("Writing local code.yaml")
    try:
        with open(os.path.join(job_folder_path, "code.yaml"), "r") as f:
            code_yaml = YAML().load(f)
    except Exception:
        code_yaml = round_trip_load("---\ncodebases: []")

    code_array = code_yaml.get("codebases", [])
    code_array.append(codebase_yaml)
    code_yaml["codebases"] = code_array
    with open(os.path.join(job_folder_path, "code.yaml"), "w") as f:
        y = YAML()
        code_yaml.fa.set_block_style()
        y.explicit_start = True
        y.default_flow_style = False
        y.dump(code_yaml, f)

    with open(os.path.join(provider_job_folder_path, "code.yaml"), "w") as f:
        y = YAML()
        code_yaml.fa.set_block_style()
        y.explicit_start = True
        y.default_flow_style = False
        y.dump(code_yaml, f)

    def get_codebase_folder_path(base_path):
        path = os.path.abspath(os.path.join(base_path, "code", run_name, checksum, ""))
        os.makedirs(path, exist_ok=True)
        return path

    local_codebase_folder_path = get_codebase_folder_path(
        monkey_global.MONKEYFS_LOCAL_PATH)
    provider_codebase_folder_path = get_codebase_folder_path(monkeyfs_path)

    logger.info(f"Already uploaded: {already_uploaded}")

    if not already_uploaded:
        local_path = os.path.join(local_codebase_folder_path,
                                  "code" + codebase_extension)
        logger.info(f"Local Path: {local_path}")
        destination_path = os.path.join(local_codebase_folder_path,
                                        "code" + codebase_extension)
        FileStorage(request.stream).save(destination_path)

        logger.info(f"Saved file to: {destination_path}")
        with open(os.path.join(local_codebase_folder_path, "code.yaml"), "w") as f:
            y = YAML()
            code_yaml.fa.set_block_style()
            y.explicit_start = True
            y.default_flow_style = False
            y.dump(code_yaml, f)
        logger.info("Syncing codebase folder")
        sync_directories(local_codebase_folder_path, provider_codebase_folder_path)
        logger.info("Syncing codebase folder: DONE")
    else:
        logger.info("Skipping uploading codebase")

    return jsonify({"msg": "Successfully uploaded codebase", "success": True})


@dispatch_routes.route('/upload/persist', methods=["POST"])
def upload_persist():
    logger.info("Received upload persist request")
    job_uid = request.args.get('job_uid', None)
    provider = request.args.get('provider', None)

    if job_uid is None or provider is None:
        return jsonify({"msg": "Did not provide job_uid or provider", "success": False})
    monkey = monkey_global.get_monkey()
    monkeyfs_path = get_local_filesystem_for_provider(provider)
    create_folder_path = os.path.join(monkeyfs_path, "jobs", job_uid)
    os.makedirs(create_folder_path, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".tmp") as temp_file:
        FileStorage(request.stream).save(temp_file.name)
        persist_tar = tarfile.open(temp_file.name, "r")
        persist_tar.extractall(path=create_folder_path)

    return jsonify({"msg": "Successfully uploaded codebase", "success": True})


@dispatch_routes.route('/submit/job')
def submit_job():
    job_args = copy.deepcopy(request.get_json())
    logger.info("Received job to submit: {}".format(job_args["job_uid"]))
    job_uid = job_args["job_uid"]

    foreground = job_args["foreground"]
    logger.info(f"Foreground: {foreground}")
    provider = job_args["provider"]
    monkey = monkey_global.get_monkey()
    monkeyfs_path = get_local_filesystem_for_provider(provider)
    job_folder_path = os.path.join(monkey_global.MONKEYFS_LOCAL_PATH, "jobs", job_uid)
    provider_job_folder_path = os.path.join(monkeyfs_path, "jobs", job_uid)

    with open(os.path.join(job_folder_path, "job.yaml"), "w") as f:
        y = YAML()
        y.explicit_start = True
        y.default_flow_style = False
        y.dump(job_args, f)

    with open(os.path.join(provider_job_folder_path, "job.yaml"), "w") as f:
        y = YAML()
        y.explicit_start = True
        y.default_flow_style = False
        y.dump(job_args, f)

    success, msg = monkey.submit_job(job_args, foreground=foreground)
    res = {"msg": msg, "success": success}

    logger.info("Finished submitting job")
    return jsonify(res)

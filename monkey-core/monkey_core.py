#!/usr/bin/env python3
import argparse
import concurrent.futures
import copy
import logging
import os
import random
import string
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from datetime import datetime

import yaml
from flask import Flask, jsonify, request, send_file
from ruamel.yaml import YAML, round_trip_load
from werkzeug.datastructures import FileStorage

import monkey_global
from monkey import Monkey
from setup_scripts.utils import get_monkey_fs, sync_directories

application = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

log_format = '%(asctime)s[%(name)s]:[%(levelname)s]: %(message)s'
log_date_format = "%m-%d %H:%M:%S"
logger = logging.getLogger('core')
hdlr = logging.FileHandler(monkey_global.LOG_FILE)
formatter = logging.Formatter(log_format, log_date_format)
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)
logger = logging.getLogger('monkey')
hdlr = logging.FileHandler(monkey_global.LOG_FILE)
formatter = logging.Formatter(log_format, log_date_format)
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)
logger = logging.getLogger('mongo')
hdlr = logging.FileHandler(monkey_global.LOG_FILE)
formatter = logging.Formatter(log_format, log_date_format)
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
hdlr = logging.FileHandler(monkey_global.LOG_FILE)
formatter = logging.Formatter(log_format, log_date_format)
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)

date_format = "monkey-%y-%m-%d-"
instance_number = 0
last_date = datetime.now().strftime(date_format)

lock = threading.Lock()
monkey = Monkey()

UNIQUE_UIDS = True

MONKEYFS_LOCAL_PATH = "ansible/monkeyfs"


def get_local_filesystem_for_provider(provider_name):
    found_provider = None
    for provider in monkey.providers:
        if provider.name == provider_name:
            found_provider = provider

    if found_provider is None:
        logger.info("Failed to find provider with specified name for job")
        return None
    local_filesystem_path = found_provider.get_local_filesystem_path()
    return local_filesystem_path


@application.route('/ping')
def ping():
    return 'pong!'


@application.route('/get/new_job_uid')
def get_new_job_uid():
    with lock:
        global date_format, instance_number, last_date
        new_date = datetime.now().strftime(date_format)
        if new_date != last_date:
            last_date = new_date
            instance_number = 1
        else:
            logger.info(
                f"Would be instance {last_date + str(instance_number + 1)}")
            pass
            instance_number += 1
        if UNIQUE_UIDS == True:
            return last_date + str(instance_number) + "-" + ''.join(
                random.choice(string.ascii_lowercase) for _ in range(3))
    return last_date + str(instance_number)


@application.route('/get/job_uid')
def get_job_uid():
    job_uid = request.args.get("job_uid", None)
    if job_uid is None:
        return jsonify({"success": False, "msg": "No job_uid provided"})
    job_uid = monkey.get_job_uid(job_uid)
    if job_uid is None:
        return jsonify({"success": False, "msg": "No job_uid provided"})
    else:
        return jsonify({
            "success": True,
            "msg": "Found matching job",
            "job_uid": job_uid
        })


@application.route('/get/job_info')
def get_job_info():
    job_uid = request.args.get("job_uid", None)
    if job_uid is None:
        return jsonify({"success": False, "msg": "No job_uid provided"})
    else:
        return jsonify({
            "success": True,
            "msg": "Found matching job",
            "job_info": monkey.get_job_info(job_uid)
        })


@application.route('/get/job_config')
def get_job_config():
    job_uid = request.args.get("job_uid", None)
    if job_uid is None:
        return jsonify({"success": False, "msg": "No job_uid provided"})
    else:
        job_config = monkey.get_job_config(job_uid)
        return jsonify({
            "success": True,
            "msg": "Found experiment config",
            "job_config": job_config
        })


@application.route('/get/job/output')
def get_job_output():
    job_uid = request.args.get("job_uid", None)
    if job_uid is None:
        return jsonify({"success": False, "msg": "No job_uid provided"})
    else:
        logger.info(f"Getting output for {job_uid}")
        job_folder_path = os.path.join(MONKEYFS_LOCAL_PATH, "jobs", job_uid)
        job_yaml_file = os.path.join(job_folder_path, "job.yaml")
        logger.info(job_yaml_file)
        try:
            with open(job_yaml_file, 'r') as job_file:
                job_yaml = yaml.load(job_file, Loader=yaml.FullLoader)
                logger.info(job_yaml)
        except:
            logger.info(f"Unable to parse job.yml, path: {job_yaml_file}")
            raise ValueError("Could not read job file")
        provider = job_yaml["provider"]
        monkeyfs_path = get_local_filesystem_for_provider(provider)
        provider_job_folder_path = os.path.join(monkeyfs_path, "jobs", job_uid)
        logger.info(f"Syncing: {provider_job_folder_path} {job_folder_path}")
        sync_directories(os.path.join(provider_job_folder_path, ""),
                         os.path.join(job_folder_path, ""))

        persisted_items = job_yaml.get("persist", [])
        logger.info(f"Retrieving persisted items: {persisted_items}")
        with tempfile.NamedTemporaryFile(delete=False,
                                         suffix=".tar") as dir_tmp:
            code_tar = tarfile.open(dir_tmp.name, "w")
            logger.info(persisted_items)
            for f in persisted_items:
                if os.path.exists(os.path.join(job_folder_path, f)):
                    code_tar.add(os.path.join(job_folder_path, f) + "/", f)
            code_tar.close()
            tar_name = dir_tmp.name
            logger.info(tar_name)
        return send_file(tar_name)


@application.route('/list/providers')
def get_list_providers():
    providers_list = monkey.get_list_providers()
    logger.info(providers_list)
    return jsonify({"response": providers_list})


@application.route('/list/local/instances')
def get_list_local_instances():
    instances_list = monkey.get_list_local_instances()
    return jsonify({"response": instances_list})


@application.route('/list/instances')
def get_list_instances():
    args = vars(request.args)
    providers = args.get('providers', [])
    if len(providers) == 0:
        providers = [x["name"] for x in monkey.get_list_providers()]
    args["providers"] = providers

    res = dict()
    for provider_name in providers:
        instances = monkey.get_list_instances(provider_name=provider_name)
        res[provider_name] = [x.get_json() for x in instances]
    return jsonify(res)


@application.route('/list/jobs')
def get_list_jobs():
    jobs_list = monkey.get_list_jobs(request.args)
    return jsonify(jobs_list)


def existing_dir(path):
    return os.path.isdir(path)


def get_codebase_path(run_name, codebase_checksum, monkeyfs_path):
    return os.path.abspath(
        os.path.join(monkeyfs_path, "code", run_name, codebase_checksum))


def get_dataset_path(dataset_name, dataset_checksum, monkeyfs_path):
    return os.path.abspath(
        os.path.join(monkeyfs_path, "data", dataset_name, dataset_checksum))


def check_checksum_path(local_path, provider_path, directory, name, checksum):
    def get_checksum_path(base_path):
        abs_path = os.path.abspath(
            os.path.join(base_path, directory, name, checksum))
        return abs_path, existing_dir(abs_path)

    local_path, local_found = get_checksum_path(base_path=local_path)
    provider_path, provider_found = get_checksum_path(base_path=provider_path)

    logger.info(
        f"local: {local_path}, provider path: {provider_path}, local_found: {local_found}, provider_found: {provider_found}"
    )

    if local_found and not provider_found:
        sync_directories(local_path, provider_path)

    return jsonify({
        "msg": f"Found existing {directory}"
        if local_found else f"Need to upload {directory}...",
        "found": local_found,
    })


@application.route('/check/dataset')
def check_dataset():
    dataset_name = request.args.get('dataset_name', None)
    dataset_checksum = request.args.get('dataset_checksum', None)
    logger.info(f"Checking dataset: {dataset_name}:{dataset_checksum}")
    provider = request.args.get('provider', None)

    if dataset_name is None or dataset_checksum is None or provider is None:
        return jsonify({
            "msg":
            "Did not provide dataset_name or dataset_checksum or provider",
            "found": False
        })

    monkeyfs_path = get_local_filesystem_for_provider(provider)

    return check_checksum_path(local_path=MONKEYFS_LOCAL_PATH,
                               provider_path=monkeyfs_path,
                               directory="data",
                               name=dataset_name,
                               checksum=dataset_checksum)


@application.route('/upload/dataset', methods=["POST"])
def upload_dataset():
    logger.info("Received upload dataset request")
    dataset_name = request.args.get('dataset_name', None)
    dataset_checksum = request.args.get('dataset_checksum', None)
    dataset_path = request.args.get('dataset_path', None)
    dataset_extension = request.args.get('dataset_extension', None)
    provider = request.args.get('provider', None)
    dataset_yaml = {
        "dataset_name": dataset_name,
        "dataset_checksum": dataset_checksum,
        "dataset_path": dataset_path,
        "dataset_extension": dataset_extension,
    }
    logger.info(dataset_yaml)
    if dataset_name is None or dataset_checksum is None or dataset_path is None \
            or dataset_extension is None or provider is None:
        return jsonify({
            "msg":
            "Did not provide dataset_name or dataset_checksum or dataset_path or dataset_extension or provider",
            "success": False
        })
    monkeyfs_path = get_local_filesystem_for_provider(provider)
    local_path = get_dataset_path(dataset_name=dataset_name,
                                  dataset_checksum=dataset_checksum,
                                  monkeyfs_path=MONKEYFS_LOCAL_PATH)

    provider_path = get_dataset_path(dataset_name=dataset_name,
                                     dataset_checksum=dataset_checksum,
                                     monkeyfs_path=monkeyfs_path)

    doc_yaml_path = os.path.join(local_path, "dataset.yaml")
    os.makedirs(local_path, exist_ok=True)
    FileStorage(request.stream).save(
        os.path.join(local_path, "data" + dataset_extension))
    logger.info("Saved file to: {}".format(
        os.path.join(local_path, "data" + dataset_extension)))
    with open(doc_yaml_path, "w") as doc_yaml_file:
        yaml.dump(dataset_yaml, doc_yaml_file)
    sync_directories(local_path, provider_path)
    return jsonify({"msg": "Successfully uploaded dataset", "success": True})


@application.route('/check/codebase')
def check_codebase():
    run_name = request.args.get('run_name', None)
    codebase_checksum = request.args.get('codebase_checksum', None)
    logger.info("Checking codebase: {}:{}".format(run_name, codebase_checksum))
    provider = request.args.get('provider', None)

    if run_name is None or codebase_checksum is None or provider is None:
        return jsonify({
            "msg": "Did not provide run_name or codebase_checksum or provider",
            "found": False
        })

    monkeyfs_path = get_local_filesystem_for_provider(provider)
    return check_checksum_path(local_path=MONKEYFS_LOCAL_PATH,
                               provider_path=monkeyfs_path,
                               directory="code",
                               name=run_name,
                               checksum=codebase_checksum)


@application.route('/upload/codebase', methods=["POST"])
def upload_codebase():
    job_uid = request.args.get('job_uid', None)
    provider = request.args.get('provider', None)
    run_name = request.args.get('run_name', None)
    checksum = request.args.get('codebase_checksum', None)
    already_uploaded = request.args.get("already_uploaded", False)
    codebase_extension = request.args.get('codebase_extension', None)

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
        "codebase_extension": codebase_extension
    }

    logger.info(f"Received upload codebase request: {job_uid}")
    if job_uid is None or provider is None:
        return jsonify({
            "msg": "Did not provide job_uid or provider",
            "success": False
        })
    monkeyfs_path = get_local_filesystem_for_provider(provider)

    job_folder_path = os.path.join(MONKEYFS_LOCAL_PATH, "jobs", job_uid)
    provider_job_folder_path = os.path.join(monkeyfs_path, "jobs", job_uid)
    os.makedirs(os.path.join(job_folder_path, "logs"), exist_ok=True)
    os.makedirs(os.path.join(provider_job_folder_path, "logs"), exist_ok=True)
    if not os.path.exists(os.path.join(job_folder_path, "logs", "run.log")):
        with open(os.path.join(job_folder_path, "logs", "run.log"), "a") as f:
            f.write("Initializing machines...")
    if not os.path.exists(
            os.path.join(provider_job_folder_path, "logs", "run.log")):
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
        path = os.path.abspath(
            os.path.join(base_path, "code", run_name, checksum, ""))
        os.makedirs(path, exist_ok=True)
        return path

    local_codebase_folder_path = get_codebase_folder_path(MONKEYFS_LOCAL_PATH)
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
        with open(os.path.join(local_codebase_folder_path, "code.yaml"),
                  "w") as f:
            y = YAML()
            code_yaml.fa.set_block_style()
            y.explicit_start = True
            y.default_flow_style = False
            y.dump(code_yaml, f)
        logger.info("Syncing codebase folder")
        sync_directories(local_codebase_folder_path,
                         provider_codebase_folder_path)
        logger.info("Syncing codebase folder: DONE")
    else:
        logger.info("Skipping uploading codebase")

    return jsonify({"msg": "Successfully uploaded codebase", "success": True})


@application.route('/upload/persist', methods=["POST"])
def upload_persist():
    logger.info("Received upload persist request")
    job_uid = request.args.get('job_uid', None)
    provider = request.args.get('provider', None)

    if job_uid is None or provider is None:
        return jsonify({
            "msg": "Did not provide job_uid or provider",
            "success": False
        })
    monkeyfs_path = get_local_filesystem_for_provider(provider)
    create_folder_path = os.path.join(monkeyfs_path, "jobs", job_uid)
    os.makedirs(create_folder_path, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".tmp") as temp_file:
        FileStorage(request.stream).save(temp_file.name)
        persist_tar = tarfile.open(temp_file.name, "r")
        persist_tar.extractall(path=create_folder_path)

    return jsonify({"msg": "Successfully uploaded codebase", "success": True})


@application.route('/submit/job')
def submit_job():
    job_args = copy.deepcopy(request.get_json())
    logger.info("Received job to submit: {}".format(job_args["job_uid"]))
    job_uid = job_args["job_uid"]

    foreground = job_args["foreground"]
    logger.info(f"Foreground: {foreground}")
    provider = job_args["provider"]
    monkeyfs_path = get_local_filesystem_for_provider(provider)
    job_folder_path = os.path.join(MONKEYFS_LOCAL_PATH, "jobs", job_uid)
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


@application.route('/state')
def get_state():
    return None


@application.route('/log')
@application.route('/logs')
def get_logs():
    def logs():
        with open('/var/log/monkey-client.log', 'r') as log_file:
            while True:
                yield log_file.read()
                time.sleep(1)

    return application.response_class(logs(), mimetype='text/plain')


def parse_args(args):
    parser = argparse.ArgumentParser(description='For extra commands')

    parser.add_argument("--dev",
                        "-d",
                        required=False,
                        default=False,
                        action="store_true",
                        dest="dev",
                        help="Auto restart core when files modified")
    parser.add_argument("--quiet",
                        "-q",
                        required=False,
                        default=None,
                        action="store_true",
                        dest="quiet",
                        help="Run quietly for all printouts")
    parser.add_argument("--ansible-quiet",
                        "-qa",
                        required=False,
                        default=None,
                        action="store_true",
                        dest="quietansible",
                        help="Run quietly for all ansible printouts")
    parser.add_argument("--periodic-quiet",
                        "-qp",
                        required=False,
                        default=None,
                        action="store_true",
                        dest="quietperiodic",
                        help="Run quietly for all periodic printouts")
    parser.add_argument("--log-file",
                        required=False,
                        default=None,
                        dest="log_file",
                        help="Run quietly for all printouts")
    parsed_args, remainder = parser.parse_known_args(args)
    if parsed_args.quiet is not None:
        monkey_global.QUIET = parsed_args.quiet
        monkey_global.QUIET_ANSIBLE = parsed_args.quiet
        monkey_global.QUIET_PERIODIC_PRINTOUT = parsed_args.quiet

    if parsed_args.quietansible is not None:
        logger.info("Running with Quiet ansible")
        monkey_global.QUIET_ANSIBLE = parsed_args.quietansible

    if parsed_args.quietperiodic is not None:
        monkey_global.QUIET_PERIODIC_PRINTOUT = parsed_args.quietperiodic
        logger.info("Running with Quiet periodic")

    if parsed_args.log_file is not None:
        monkey_global.LOG_FILE = parsed_args.log_file

    logger.info(f"Logging to { monkey_global.LOG_FILE }")
    logging.info("Starting Monkey Core logs...")
    return parsed_args


def main():
    parsed_args = parse_args(sys.argv[1:])
    if parsed_args.dev:
        logger.info("\n\nStarting in debug mode...\n\n")
        application.run(host='0.0.0.0',
                        port=9990,
                        debug=True,
                        use_reloader=True)
    else:
        application.run(host='0.0.0.0', port=9990)
    return 0


if __name__ == '__main__':
    logger.info("Starting Monkey Core")
    exit(main())

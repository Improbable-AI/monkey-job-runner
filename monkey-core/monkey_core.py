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
from flask import Flask, jsonify, request
from werkzeug.datastructures import FileStorage

import monkey_global
from monkey import Monkey
from setup_scripts.utils import get_monkey_fs

application = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

date_format = "monkey-%y-%m-%d-"
instance_number = 0
last_date = datetime.now().strftime(date_format)

lock = threading.Lock()
monkey = Monkey()

UNIQUE_UIDS = True


def get_local_filesystem_for_provider(provider_name):
    found_provider = None
    for provider in monkey.providers:
        if provider.name == provider_name:
            found_provider = provider

    if found_provider is None:
        print("Failed to find provider with specified name for job")
        return None
    local_filesystem_path = found_provider.get_local_filesystem_path()
    return local_filesystem_path


@application.route('/ping')
def ping():
    return 'pong!'


@application.route('/get/job_uid')
def get_job_uid():
    with lock:
        global date_format, instance_number, last_date
        new_date = datetime.now().strftime(date_format)
        if new_date != last_date:
            last_date = new_date
            instance_number = 1
        else:
            print("Would be instance", last_date + str(instance_number + 1))
            pass
            instance_number += 1
        if UNIQUE_UIDS == True:
            return last_date + str(instance_number) + "-" + ''.join(
                random.choice(string.ascii_lowercase) for _ in range(3))
        return last_date + str(instance_number)


@application.route('/list/providers')
def get_list_providers():
    providers_list = monkey.get_list_providers()
    print(providers_list)
    return jsonify({"response": providers_list})


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


@application.route('/check/dataset')
def check_dataset():
    dataset_name = request.args.get('dataset_name', None)
    dataset_checksum = request.args.get('dataset_checksum', None)
    print("Checking dataset: {}:{}".format(dataset_name, dataset_checksum))
    provider = request.args.get('provider', None)

    if dataset_name is None or dataset_checksum is None or provider is None:
        return jsonify({
            "msg":
            "Did not provide dataset_name or dataset_checksum or provider",
            "found": False
        })

    monkeyfs_path = get_local_filesystem_for_provider(provider)
    print("Monkeyfs path", monkeyfs_path, "provider", provider)
    dataset_path = os.path.join(monkeyfs_path, "data", dataset_name,
                                dataset_checksum)

    return jsonify({
        "msg":
        "Found existing dataset.  Continuing..."
        if os.path.isdir(dataset_path) else "Need to upload dataset...",
        "found":
        os.path.isdir(dataset_path),
    })


@application.route('/submit/job')
def submit_job():
    job_args = copy.deepcopy(request.get_json())
    print("Received job to submit:", job_args["job_uid"])

    foreground = job_args["foreground"]
    print("Foreground", foreground)

    success, msg = monkey.submit_job(job_args, foreground=foreground)
    res = {"msg": msg, "success": success}

    print("Finished submitting job")
    return jsonify(res)


@application.route('/upload/codebase', methods=["POST"])
def upload_codebase():
    job_uid = request.args.get('job_uid', None)
    provider = request.args.get('provider', None)
    print("Received upload codebase request:", job_uid)
    if job_uid is None or provider is None:
        return jsonify({
            "msg": "Did not provide job_uid or provider",
            "success": False
        })
    monkeyfs_path = get_local_filesystem_for_provider(provider)
    create_folder_path = os.path.join(monkeyfs_path, "jobs", job_uid)
    os.makedirs(os.path.join(create_folder_path, "logs"), exist_ok=True)
    if not os.path.exists(os.path.join(create_folder_path, "logs", "run.log")):
        with open(os.path.join(create_folder_path, "logs", "run.log"),
                  "w") as f:
            pass
    FileStorage(request.stream).save(
        os.path.join(create_folder_path, "code.tar"))
    print("Saved file to: {}".format(
        os.path.join(create_folder_path, "code.tar")))
    return jsonify({"msg": "Successfully uploaded codebase", "success": True})


@application.route('/upload/persist', methods=["POST"])
def upload_persist():
    print("Received upload persist request")
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


@application.route('/upload/dataset', methods=["POST"])
def upload_dataset():
    print("Received upload dataset request")
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
    print(dataset_name, dataset_checksum, dataset_path)
    if dataset_name is None or dataset_checksum is None or dataset_path is None \
            or dataset_extension is None or provider is None:
        return jsonify({
            "msg":
            "Did not provide dataset_name or dataset_checksum or dataset_path or dataset_extension or provider",
            "success": False
        })
    monkeyfs_path = get_local_filesystem_for_provider(provider)
    create_folder_path = os.path.join(monkeyfs_path, "data", dataset_name,
                                      dataset_checksum)
    doc_yaml_path = os.path.join(create_folder_path, "dataset.yaml")
    os.makedirs(create_folder_path, exist_ok=True)
    FileStorage(request.stream).save(
        os.path.join(create_folder_path, "data" + dataset_extension))
    print("Saved file to: {}".format(
        os.path.join(create_folder_path, "data" + dataset_extension)))
    with open(doc_yaml_path, "w") as doc_yaml_file:
        yaml.dump(dataset_yaml, doc_yaml_file)
    return jsonify({"msg": "Successfully uploaded dataset", "success": True})


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
                        help="Run quietly for all printouts")
    parser.add_argument("--log-file",
                        required=False,
                        default=None,
                        dest="log_file",
                        help="Run quietly for all printouts")
    parsed_args, remainder = parser.parse_known_args(args)
    if parsed_args.quiet is not None:
        monkey_global.QUIET = parsed_args.quiet
        monkey_global.QUIET_ANSIBLE = parsed_args.quiet

    if parsed_args.quietansible is not None:
        monkey_global.QUIET_ANSIBLE = parsed_args.quietansible

    if parsed_args.log_file is not None:
        monkey_global.LOG_FILE = parsed_args.log_file

    print("Logging to ", monkey_global.LOG_FILE)
    logging.basicConfig(filename=monkey_global.LOG_FILE, level=logging.DEBUG)
    logging.info("Starting Monkey Core logs...")
    return parsed_args


def main():
    parsed_args = parse_args(sys.argv[1:])
    if parsed_args.dev:
        print("\n\nStarting in debug mode...\n\n")
        application.run(host='0.0.0.0',
                        port=9990,
                        debug=True,
                        use_reloader=True)
    else:
        application.run(host='0.0.0.0', port=9990)
    return 0


if __name__ == '__main__':
    exit(main())

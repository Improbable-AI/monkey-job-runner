from flask import Flask, jsonify, request
application = Flask(__name__)

import os
import time
import threading
import copy

from monkey import Monkey
from werkzeug.datastructures import FileStorage
import tempfile
import yaml
import concurrent.futures
from datetime import datetime
import tarfile
import subprocess
import random
import string
date_format = "monkey-%y-%m-%d-"
instance_number = 0
last_date = datetime.now().strftime(date_format)

lock = threading.Lock()
monkey = Monkey()

UNIQUE_UIDS = True

print("Checking for GCP MonkeyFS...")
# TODO(alamp): make it run with multiple shared filesystems
# TODO(alamp): dynamically search for filesystem name
fs_output = subprocess.check_output("df | grep monkeyfs | awk '{print $9}'", shell=True).decode("utf-8")
print(fs_output)
if fs_output is None or fs_output == "":
    raise LookupError("Unable to find shared mounted gcp filesyste monkeyfs")
GCP_MONKEY_FS = fs_output.split("\n")[0]

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
            print("Would be instance",last_date + str(instance_number + 1))
            pass
            instance_number += 1
        if UNIQUE_UIDS == True:
            return last_date + str(instance_number) + "-" + ''.join(random.choice(string.ascii_lowercase) for _ in range(3))
        return last_date + str(instance_number)

@application.route('/list/providers')
def get_list_providers():
    providers_list = monkey.get_list_providers()
    print(providers_list)
    return jsonify(providers_list)

@application.route('/list/instances')
def get_list_instances():
    print("Request")
    providers = request.args.get('providers', [])
    if len(providers) == 0:
        providers = [x["name"] for x in monkey.get_list_providers()]
    
    print("Looking up instances for providers: {}".format(providers))
    res = dict()
    for provider_name in providers:
        instances = monkey.get_list_instances(provider_name=provider_name)
        res[provider_name] = [x.get_json() for x in instances]
    
    print(res)
    return jsonify(res)

@application.route('/list/jobs')
def get_list_jobs():
    providers_list = monkey.get_list_providers()
    print(providers_list)
    return jsonify(providers_list)

@application.route('/check/dataset')
def check_dataset():
    print("Checking dataset: {}".format(request.args))
    dataset_name = request.args.get('dataset_name', None)
    dataset_checksum = request.args.get('dataset_checksum', None)
    
    if dataset_name is None or dataset_checksum is None:
        return jsonify({
            "msg": "Did not provide dataset_name or dataset_checksum",
            "found": False
        })

    dataset_path = os.path.join(GCP_MONKEY_FS, "data", dataset_name, dataset_checksum)
    
    return jsonify({
        "msg": "Found existing dataset.  Continuing..." if os.path.isdir(dataset_path) else "Need to upload dataset...",
        "found": os.path.isdir(dataset_path),
    })

@application.route('/submit/job')
def submit_job():
    job_args = copy.deepcopy(request.get_json())
    print("Received job to submit:", job_args["job_uid"])

    foreground = job_args["foreground"]
    print("Foreground", foreground)

    success, msg = monkey.submit_job(job_args, foreground=foreground)
    res = {
        "msg": msg,
        "success": success
    }
    
    print("returning:", res)
    return jsonify(res)

@application.route('/upload/codebase', methods=["POST"])
def upload_codebase():
    job_uid = request.args.get('job_uid', None)
    print("Received upload codebase request:", job_uid)
    if job_uid is None:
        return jsonify({
            "msg": "Did not provide job_uid",
            "success": False
        })
    create_folder_path = os.path.join(GCP_MONKEY_FS, "jobs", job_uid)
    os.makedirs(os.path.join(create_folder_path, "logs"), exist_ok= True)
    if not os.path.exists(os.path.join(create_folder_path, "logs", "run.log")):
        with open(os.path.join(create_folder_path, "logs", "run.log"), "w") as f:
            pass
    FileStorage(request.stream).save(os.path.join(create_folder_path, "code.tar"))
    print("Saved file to: {}".format(os.path.join(create_folder_path, "code.tar")))
    return jsonify({
            "msg": "Successfully uploaded codebase",
            "success": True
        })

@application.route('/upload/persist', methods=["POST"])
def upload_persist():
    print("Received upload persist request")
    job_uid = request.args.get('job_uid', None)
    if job_uid is None:
        return jsonify({
            "msg": "Did not provide job_uid or name",
            "success": False
        })
    create_folder_path = os.path.join(GCP_MONKEY_FS, "jobs", job_uid)
    os.makedirs(create_folder_path, exist_ok= True)

    with tempfile.NamedTemporaryFile(suffix=".tmp") as temp_file:
        FileStorage(request.stream).save(temp_file.name)
        persist_tar = tarfile.open(temp_file.name, "r")
        persist_tar.extractall(path=create_folder_path)

    return jsonify({
            "msg": "Successfully uploaded codebase",
            "success": True
        })

@application.route('/upload/dataset', methods=["POST"])
def upload_dataset():
    print("Received upload dataset request")
    dataset_name = request.args.get('dataset_name', None)
    dataset_checksum = request.args.get('dataset_checksum', None)
    dataset_path = request.args.get('dataset_path', None)
    dataset_extension = request.args.get('dataset_extension', None)
    dataset_yaml = {
        "dataset_name": dataset_name,
        "dataset_checksum": dataset_checksum,
        "dataset_path": dataset_path,
        "dataset_extension": dataset_extension,
    }
    print(dataset_name, dataset_checksum, dataset_path)
    if dataset_name is None or dataset_checksum is None or dataset_path is None or dataset_extension is None:
        return jsonify({
            "msg": "Did not provide dataset_name or dataset_checksum or dataset_path or dataset_extension",
            "success": False
        })
    create_folder_path = os.path.join(GCP_MONKEY_FS, "data", dataset_name, dataset_checksum)
    doc_yaml_path = os.path.join(create_folder_path, "dataset.yaml")
    os.makedirs(create_folder_path, exist_ok= True)
    FileStorage(request.stream).save(os.path.join(create_folder_path, "data" + dataset_extension))
    print("Saved file to: {}".format(os.path.join(create_folder_path, "data" + dataset_extension)))
    with open(doc_yaml_path, "w") as doc_yaml_file:
        yaml.dump(dataset_yaml, doc_yaml_file)
    return jsonify({
            "msg": "Successfully uploaded dataset",
            "success": True
        })

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





if __name__ == '__main__':
    application.run(host='0.0.0.0', port=9990, debug=True)


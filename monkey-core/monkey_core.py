from flask import Flask, jsonify, request
application = Flask(__name__)

import os
import time
import threading

from monkey import Monkey
import werkzeug
from werkzeug.datastructures import FileStorage
import tempfile
import yaml
monkey = Monkey()

MONKEY_FS = "/Users/avery/Developer/projects/monkey-project/monkey-core/monkeyfs"

@application.route('/ping')
def ping():
    return 'pong!'

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

    dataset_path = os.path.join(MONKEY_FS, "data", dataset_name, dataset_checksum)
    
    return jsonify({
        "msg": "Found existing dataset" if os.path.isdir(dataset_path) else "Need to upload dataset",
        "found": os.path.isdir(dataset_path),
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
    create_folder_path = os.path.join(MONKEY_FS, "data", dataset_name, dataset_checksum)
    doc_yaml_path = os.path.join(create_folder_path, "dataset.yaml")
    os.makedirs(create_folder_path, exist_ok= True)
    FileStorage(request.stream).save(os.path.join(create_folder_path, "data" + dataset_extension))
    print("Saved file to: {}".format(os.path.join(create_folder_path, "data" + dataset_extension)))
    with open(doc_yaml_path, "w") as doc_yaml_file:
        yaml.dump(dataset_yaml, doc_yaml_file)
    return jsonify({
            "msg": "Did not provide dataset_name or dataset_checksum or dataset_path",
            "success": False
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


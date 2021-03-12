import logging
import os
import tarfile
import tempfile

import yaml
from core import monkey_global
from core.routes.utils import (get_local_filesystem_for_provider,
                               sync_directories)
from flask import Blueprint, jsonify, request, send_file
from ruamel.yaml import YAML, round_trip_load

info_routes = Blueprint("info_routes", __name__)

logger = logging.getLogger(__name__)


@info_routes.route('/ping')
def ping():
    return 'pong!'


@info_routes.route('/list/providers')
def get_list_providers():
    monkey = monkey_global.get_monkey()
    providers_list = monkey.get_list_providers()
    logger.info(providers_list)
    return jsonify({"response": providers_list})


@info_routes.route('/list/local/instances')
def get_list_local_instances():
    monkey = monkey_global.get_monkey()
    instances_list = monkey.get_list_local_instances()
    return jsonify({"response": instances_list})


@info_routes.route('/list/instances')
def get_list_instances():
    monkey = monkey_global.get_monkey()
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


@info_routes.route('/list/jobs')
def get_list_jobs():
    monkey = monkey_global.get_monkey()
    jobs_list = monkey.get_list_jobs(request.args)
    return jsonify(jobs_list)


@info_routes.route('/get/job_uid')
def get_job_uid():
    monkey = monkey_global.get_monkey()
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


@info_routes.route('/get/job_info')
def get_job_info():
    monkey = monkey_global.get_monkey()
    job_uid = request.args.get("job_uid", None)
    if job_uid is None:
        return jsonify({"success": False, "msg": "No job_uid provided"})
    else:
        return jsonify({
            "success": True,
            "msg": "Found matching job",
            "job_info": monkey.get_job_info(job_uid)
        })


@info_routes.route('/get/job_config')
def get_job_config():
    monkey = monkey_global.get_monkey()
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


@info_routes.route('/get/job/output')
def get_job_output():
    monkey = monkey_global.get_monkey()
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
        monkeyfs_path = get_local_filesystem_for_provider(monkey, provider)
        provider_job_folder_path = os.path.join(monkeyfs_path, "jobs", job_uid)
        logger.info(f"Syncing: {provider_job_folder_path} {job_folder_path}")
        sync_directories(os.path.join(provider_job_folder_path, ""),
                         os.path.join(job_folder_path, ""))

        persisted_items = job_yaml.get("persist", [])
        logger.info(f"Retrieving persisted items: {persisted_items}")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tar") as dir_tmp:
            code_tar = tarfile.open(dir_tmp.name, "w")
            logger.info(persisted_items)
            for f in persisted_items:
                if os.path.exists(os.path.join(job_folder_path, f)):
                    code_tar.add(os.path.join(job_folder_path, f) + "/", f)
            code_tar.close()
            tar_name = dir_tmp.name
            logger.info(tar_name)
        return send_file(tar_name)

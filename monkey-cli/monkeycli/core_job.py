import fnmatch
import glob
import os
import shutil
import tarfile
import tempfile

import requests
from checksumdir import dirhash
from termcolor import colored

from monkeycli.utils import build_url


def check_or_upload_dataset(dataset, provider_name, compression_type="tar"):
    print("Uploading dataset...")
    dataset_name = dataset["name"]
    dataset_path = dataset["path"]
    dataset_checksum = dirhash(dataset_path)
    print("Dataset checksum: {}".format(dataset_checksum))

    if dataset.get("compression", "tar"):
        compression_map = {"tar": ".tar", "gztar": ".tar.gz", "zip": ".zip"}
        compression_type = dataset.get("compression", "tar")
        compression_suffix = compression_map[compression_type]

    dataset_params = {
        "dataset_name": dataset_name,
        "dataset_checksum": dataset_checksum,
        "dataset_path": dataset_path,
        "dataset_extension": compression_suffix,
        "provider": provider_name
    }
    r = requests.get(build_url("check/dataset"), params=dataset_params)
    dataset_found, msg = r.json().get("found", False), r.json().get("msg", "")
    print(msg)
    if dataset_found == False:
        with tempfile.NamedTemporaryFile() as dir_tmp:
            print("Compressing Dataset...")
            shutil.make_archive(dir_tmp.name, compression_type, dataset_path)
            compressed_name = dir_tmp.name + compression_suffix
            print(compressed_name)
            try:
                with open(compressed_name, "rb") as compressed_dataset:
                    r = requests.post(build_url("upload/dataset/"),
                                      data=compressed_dataset,
                                      params=dataset_params,
                                      allow_redirects=True)
                    success = r.json()["success"]
                    print("Upload Dataset Success: ", success)
            except:
                print("Upload failure")
            finally:
                os.remove(compressed_name)
    dataset_filename = "data" + compression_suffix
    return dataset_checksum, dataset_filename


def upload_persisted_folder(persist, job_uid, provider_name):
    print("Uploading persisted_folder...")

    if type(persist) is str:
        persist_name = persist
        code_path = persist
        ignore_filters = []
    elif type(persist) is dict:
        persist_name = persist["name"]
        code_path = persist["path"]
        ignore_filters = persist.get("ignore", [])

    all_files = set([
        y.strip("/") for y in
        [x.strip(".") for x in glob.glob(code_path + "/**", recursive=True)]
    ])
    filenames = (n for n in all_files if not any(
        fnmatch.fnmatch(n, ignore) for ignore in ignore_filters))
    all_files = sorted(list(filenames))
    print("Persisting: ", all_files)
    if "" in all_files:
        all_files.remove("")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tar") as dir_tmp:
        code_tar = tarfile.open(dir_tmp.name, "w")
        code_tar.add(persist_name)
        # for file in all_files:
        #     code_tar.add(file)
        code_tar.close()
        success = False
        try:
            with open(dir_tmp.name, "rb") as compressed_persist:
                r = requests.post(build_url("upload/persist"),
                                  data=compressed_persist,
                                  params={
                                      "job_uid": job_uid,
                                      "provider": provider_name
                                  },
                                  allow_redirects=True)
                success = r.json()["success"]
                print(
                    "Upload Persisted Folder:",
                    colored("Successful", "green") if success else colored(
                        "FAILED", "red"))
        except:
            print("Upload failure")
        if success == False:
            raise ValueError("Failed to upload codebase")
    print()


def upload_codebase(code, job_uid, provider_name):
    print("Uploading Codebase...")
    code_path = code["path"]
    ignore_filters = [x + "*" for x in code.get("ignore", [])]

    all_files = set([
        y.strip("/") for y in
        [x.strip(".") for x in glob.glob(code_path + "/**", recursive=True)]
    ])
    filenames = (n for n in all_files if not any(
        fnmatch.fnmatch(n, ignore) for ignore in ignore_filters))
    all_files = sorted(list(filenames))
    if "" in all_files:
        all_files.remove("")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tar") as dir_tmp:
        code_tar = tarfile.open(dir_tmp.name, "w")
        for file in all_files:
            code_tar.add(file)
        code_tar.close()
        success = False
        try:
            with open(dir_tmp.name, "rb") as compressed_codebase:
                r = requests.post(build_url("upload/codebase"),
                                  data=compressed_codebase,
                                  params={
                                      "job_uid": job_uid,
                                      "provider": provider_name
                                  },
                                  allow_redirects=True)
                success = r.json()["success"]
                print(
                    "Upload Codebase:",
                    colored("Successful", "green") if success else colored(
                        "FAILED", "red"))
        except:
            print("Upload failure")
        if success == False:
            raise ValueError("Failed to upload codebase")


def submit_job(job):
    print("Submitting Job: {}".format(colored(job["job_uid"], "green")))
    r = requests.get(build_url("submit/job"), json=job)
    success, msg = r.json()["success"], r.json()["msg"]
    if success == False:
        print(msg)
        raise RuntimeError(msg)

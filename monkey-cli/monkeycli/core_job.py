import fnmatch
import glob
import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile

import requests
from dirhash import dirhash
from termcolor import colored

from monkeycli.utils import build_url

compression_map = {"tar": ".tar", "gztar": ".tar.gz", "zip": ".zip"}


def check_or_upload_dataset(dataset, provider_name, compression_type="tar"):
    print("Uploading dataset...")
    dataset_name = dataset["name"]
    dataset_path = dataset["path"]
    dataset_checksum = dirhash(dataset_path, "md5")
    print("Dataset checksum: {}".format(dataset_checksum))

    if dataset.get("compression", "tar"):
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

    ignore_filters = []
    all_files = set([
        y.strip("/") for y in
        [x.strip(".") for x in glob.glob(persist + "**", recursive=True)]
    ])
    filenames = (n for n in all_files if not any(
        fnmatch.fnmatch(n, ignore) for ignore in ignore_filters))
    all_files = sorted(list(filenames))
    print("Persisting: ", all_files)
    if "" in all_files:
        all_files.remove("")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tar") as dir_tmp:
        code_tar = tarfile.open(dir_tmp.name, "w")
        code_tar.add(persist)
        for file in all_files:
            code_tar.add(file)
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


def calculate_file_list_checksum(filenames):
    hash_current = hashlib.md5()
    for fn in filenames:
        if os.path.isfile(fn):
            hash_current.update(open(fn, "rb").read())
    return hash_current.hexdigest()


def check_or_upload_codebase(code,
                             job_uid,
                             run_name,
                             provider_name,
                             compression_type="tar"):
    print("Uploading Codebase...")

    cwd = os.getcwd()

    code_path = code["path"]
    os.chdir(code_path)

    p = subprocess.run(f"git ls-files",
                       shell=True,
                       check=True,
                       capture_output=True)
    non_gitignored_files = p.stdout.decode("utf-8").split("\n")
    if p.returncode != 0:
        print("Unable to git ls-file")
        return False
    os.chdir(cwd)
    ignore_filters = [x + "*" for x in code.get("ignore", [])]

    all_files = set(non_gitignored_files)
    if "" in all_files:
        all_files.remove("")
    filenames = (n for n in all_files if not any(
        fnmatch.fnmatch(n, ignore) for ignore in ignore_filters))
    all_files = sorted(list(filenames))
    if len(all_files) == 0:
        print(
            "No files detected as staged.  Add your files to staged with git add . to make sure monkey can detect them"
        )
        exit(1)
    compression_suffix = compression_map[compression_type]
    files_checksum = calculate_file_list_checksum(all_files)
    print(f"Codebase checksum: {files_checksum}")

    codebase_params = {
        "job_uid": job_uid,
        "run_name": run_name,
        "provider": provider_name,
        "codebase_checksum": files_checksum,
        "codebase_extension": compression_suffix,
    }

    r = requests.get(build_url("check/codebase"), params=codebase_params)

    codebase_found, msg = r.json().get("found", False), r.json().get("msg", "")
    codebase_params["already_uploaded"] = codebase_found
    print(msg, "codebase_found: ", codebase_found)
    if not codebase_found:
        print("Creating codebase tar...")
        with tempfile.NamedTemporaryFile(delete=False,
                                         suffix=".tar") as dir_tmp:
            code_tar = tarfile.open(dir_tmp.name, "w")
            for f in all_files:
                try:
                    code_tar.add(f)
                except Exception as e:
                    print(f"Skipping adding: {f}\nError: {e}")

            code_tar.close()
            success = False
            try:
                with open(dir_tmp.name, "rb") as codebase_tar:
                    print(codebase_params)

                    r = requests.post(build_url("upload/codebase"),
                                      data=codebase_tar,
                                      params=codebase_params,
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
    else:
        print("Uploading codebase yaml")
        r = requests.post(build_url("upload/codebase"),
                          params=codebase_params,
                          allow_redirects=True)
        success = r.json()["success"]
        print(
            "Upload Codebase:",
            colored("Successful", "green") if success else colored(
                "FAILED", "red"))

    return codebase_params


def submit_job(job):
    print("Submitting Job: {}".format(colored(job["job_uid"], "green")))
    r = requests.get(build_url("submit/job"), json=job)
    success, msg = r.json()["success"], r.json()["msg"]
    if success == False:
        print(msg)
        raise RuntimeError(msg)

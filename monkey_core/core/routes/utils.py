import logging
import os
import subprocess

logger = logging.getLogger(__name__)
from core import monkey_global


def sync_directories(dir1, dir2):
    if not os.path.isdir(dir1):
        return False

    dir1 = os.path.join(os.path.normpath(dir1), "")
    dir2 = os.path.join(os.path.normpath(dir2), "")
    os.makedirs(dir1, exist_ok=True)
    os.makedirs(dir2, exist_ok=True)
    print(dir1)
    print(dir2)
    p = subprocess.run(f"rsync -ra {dir1} {dir2}", shell=True, check=True)
    return p.returncode == 0


def get_local_filesystem_for_provider(provider_name):
    monkey = monkey_global.get_monkey()
    found_provider = None
    for provider in monkey.providers:
        if provider.name == provider_name:
            found_provider = provider

    if found_provider is None:
        logger.info("Failed to find provider with specified name for job")
        return None
    local_filesystem_path = found_provider.get_local_filesystem_path()
    return local_filesystem_path


def get_codebase_path(run_name, codebase_checksum, monkeyfs_path):
    return os.path.abspath(
        os.path.join(monkeyfs_path, "code", run_name, codebase_checksum))


def get_dataset_path(dataset_name, dataset_checksum, monkeyfs_path):
    return os.path.abspath(
        os.path.join(monkeyfs_path, "data", dataset_name, dataset_checksum))


def existing_dir(path):
    return os.path.isdir(path)

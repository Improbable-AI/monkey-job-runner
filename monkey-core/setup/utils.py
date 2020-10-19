import os
import readline
import subprocess
from shutil import which

from mongoengine import *
from ruamel.yaml import YAML


def check_for_existing_local_command(command):
    return which(command) is not None


def load_yaml_file_as_dict(filename):
    try:
        with open(filename) as f:
            aws_vars = YAML().load(f)
            return aws_vars
    except:
        print("Failed to load ", filename)
        return dict()


def get_aws_vars():
    aws_vars_file = "ansible/aws_vars.yml"
    return load_yaml_file_as_dict(aws_vars_file)


def get_gcp_vars():
    gcp_vars_file = "ansible/gcp_vars.yml"
    return load_yaml_file_as_dict(gcp_vars_file)


def printout_ansible_events(events):
    events = [(x.get("event_data", {}).get("task", "unknown"),
               x.get("event_data", {}).get("playbook", "unknown"),
               x.get("event_data", {}).get("task_action", "unknown"),
               x.get("event_data", {}).get("task_args",
                                           "unknown"), x.get("stdout", None))
              for x in events]

    for task, playbook, action, args, stdout in events:
        print("----------------------")
        print(playbook, ":", task)
        print("Task: ", action, ", args: ", args)
        if stdout is not None and stdout != "":
            print("stdout: ", stdout, "\n")


def get_monkey_fs():
    # Check env variable MONKEYFS_PATH first
    fs_path = os.environ.get("MONKEYFS_PATH", None)
    if fs_path is not None:
        print("Found env path:", fs_path)
        # Check that the env variable is a mounted directory
        fs_output = os.system("df {} | grep '{}'".format(fs_path, fs_path))
        if fs_output == 0:
            # env filepath appears in df
            return fs_path
        print("Did not find mount aligning with fs_path:", fs_path)
    # Check for mounts
    fs_output = subprocess.check_output(
        "df ansible/monkeyfs | grep monkeyfs | awk '{print $NF}'",
        shell=True).decode("utf-8")
    print(fs_output)
    if fs_output is not None and fs_output != "":
        fs_path = fs_output.split("\n")[0]
        return fs_path
    return None


def aws_cred_file_environment(file):
    with open(file) as f:
        lines = f.readlines()
        names = [x.strip() for x in lines[0].split(",")]
        values = [x.strip() for x in lines[1].split(",")]
        d = dict(zip(names, values))

        if "Access key ID" not in d or "Secret access key" not in d:
            print("The AWS Cred File does not look like a csv cred file")
            raise ValueError(
                "The AWS Cred File does not look like a csv cred file")

        access_key_id = d["Access key ID"]
        access_key_secret = d["Secret access key"]
        return {
            "AWS_ACCESS_KEY_ID": access_key_id,
            "AWS_SECRET_ACCESS_KEY": access_key_secret,
        }


class Completer(object):
    def _listdir(self, root):
        "List directory 'root' appending the path sep arator to subdirs."
        res = []
        for name in os.listdir(root):
            path = os.path.join(root, name)
            if os.path.isdir(path):
                name += os.sep
            res.append(name)
        return res

    def _complete_path(self, path=None):
        "Perform completion of filesystem path."
        if not path:
            return self._listdir('.')
        dirname, rest = os.path.split(path)
        tmp = dirname if dirname else '.'
        res = [
            os.path.join(dirname, p) for p in self._listdir(tmp)
            if p.startswith(rest)
        ]
        # more than one match, or single match which does not exist (typo)
        if len(res) > 1 or not os.path.exists(path):
            return res
        # resolved to a single directory, so return list of files below it
        if os.path.isdir(path):
            return [os.path.join(path, p) for p in self._listdir(path)]
        # exact file match terminates this completion
        return [path + ' ']

    def complete(self, text, state):
        "Generic readline completion entry point."
        line = readline.get_line_buffer().split()
        if not line:
            return self._listdir(".")[state]
        if len(line) == 1 and len(text) != 0:
            return self._complete_path(line[-1])[state]
        return None

import json
import os
import random
import readline
import string
import subprocess
from shutil import which

from ruamel.yaml import YAML, round_trip_load


def check_for_existing_local_command(command):
    return which(command) is not None


def load_yaml_file_as_dict(filename):
    try:
        with open(filename) as f:
            aws_vars = YAML().load(f)
            return aws_vars
    except Exception:
        print("Failed to load ", filename)
        return dict()


def get_aws_vars():
    aws_vars_file = "ansible/aws_vars.yml"
    return load_yaml_file_as_dict(aws_vars_file)


def get_gcp_vars():
    gcp_vars_file = "ansible/gcp_vars.yml"
    return load_yaml_file_as_dict(gcp_vars_file)


def printout_ansible_events(events):
    events = [(x.get("event_data",
                     {}).get("task",
                             "unknown"), x.get("event_data",
                                               {}).get("playbook", "unknown"),
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


def get_input_with_defaults(prompt_phrase, prompt_name, default_value,
                            noinput):
    if noinput:
        print(f"{prompt_name} not provider. Defaulting to: {default_value}")
        return default_value
    return input(f"{prompt_phrase} ({default_value}): ") or default_value


def generate_random_monkeyfs_name():
    return "monkeyfs-" + ''.join(
        random.choice(string.ascii_lowercase) for _ in range(6))


def aws_cred_file_environment(cred_file):
    with open(cred_file) as f:
        lines = f.readlines()
        names = [x.strip() for x in lines[0].split(",")]
        values = [x.strip() for x in lines[1].split(",")]
        d = dict(zip(names, values))

        if "Access key ID" not in d or "Secret access key" not in d:
            raise ValueError(
                "The AWS Cred File does not look like a csv cred file")

        access_key_id = d["Access key ID"]
        access_key_secret = d["Secret access key"]
        return {
            "AWS_ACCESS_KEY_ID": access_key_id,
            "AWS_SECRET_ACCESS_KEY": access_key_secret,
        }


def gcp_cred_file_environment(cred_file):
    with open(cred_file) as f:
        creds = json.load(f)
        return creds


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
            os.path.join(dirname, p)
            for p in self._listdir(tmp)
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


def write_vars_file(
        raw_vars,
        provider_name,
        provider_yaml,
        file_name,
        before_comments=dict(),
        end_line_comments=dict(),
):
    vars_dict = round_trip_load(str(raw_vars))
    vars_dict.yaml_set_start_comment("\nProvider: {}".format(provider_name))

    for key, comment in before_comments.items():
        vars_dict.yaml_set_comment_before_after_key(key, before=comment)

    for key, comment in end_line_comments.items():
        vars_dict.yaml_add_eol_comment(comment, key)

    # Create filesystem bucket and pick a new id if failed
    providers = provider_yaml.get("providers", [])
    if providers is None:
        providers = []
    vars_dict.fa.set_block_style()
    providers.append(vars_dict)
    provider_yaml["providers"] = providers

    print("\nWriting to providers.yml...")
    providers_file = "providers.yml"
    write_commented_yaml_file(providers_file, provider_yaml)

    print("\nWriting aws vars file...")
    vars_file = f"ansible/{file_name}"
    write_commented_yaml_file(vars_file, vars_dict)


def write_commented_yaml_file(filename, yaml_params):
    yaml_params.fa.set_block_style()
    with open(filename, "w") as f:
        try:
            y = YAML()
            y.explicit_start = True
            y.default_flow_style = False
            y.dump(yaml_params, f)
        except Exception as e:
            print(f"Failed to write file: {filename}\n{e}")
            exit(1)

import os
import readline
import subprocess
from mongoengine import *


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
    fs_output = subprocess.check_output("df ansible/monkeyfs | grep monkeyfs | awk '{print $NF}'",
                                        shell=True).decode("utf-8")
    print(fs_output)
    if fs_output is not None and fs_output != "":
        fs_path = fs_output.split("\n")[0]
        return fs_path
    return None

def aws_cred_file_environment(file):
    print(file)
    with open(file) as f:
        lines = f.readlines()
        print(lines)
        names = lines[0].split(",")
        values = lines[1].split(",")
        print(names[2])
        print(names[3])
        
        if names[2] != "Access key ID" or names[3] != "Secret access key":
            raise ValueError("The AWS Cred File does not look like a csv cred file")

        access_key_id = values[2]
        access_key_secret = values[3]
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
        res = [os.path.join(dirname, p)
               for p in self._listdir(tmp) if p.startswith(rest)]
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

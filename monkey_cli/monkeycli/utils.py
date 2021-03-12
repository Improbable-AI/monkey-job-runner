import os
import readline
from urllib.parse import urljoin

from monkeycli.globals import MONKEY_CORE_URL


def build_url(path):
    return urljoin(MONKEY_CORE_URL, path.strip("/"))


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


MONKEY_STATE_QUEUED = "QUEUED"
MONKEY_STATE_DISPATCHING = "DISPATCHING"
MONKEY_STATE_DISPATCHING_MACHINE = "DISPATCHING_MACHINE"
MONKEY_STATE_DISPATCHING_INSTALLS = "DISPATCHING_INSTALLS"
MONKEY_STATE_DISPATCHING_SETUP = "DISPATCHING_SETUP"
MONKEY_STATE_RUNNING = "RUNNING"
MONKEY_STATE_CLEANUP = "CLEANING_UP"
MONKEY_STATE_FINISHED = "FINISHED"


def human_readable_state(state):
    if state == MONKEY_STATE_QUEUED:
        return "Queued"
    elif state == MONKEY_STATE_DISPATCHING:
        return "Creating Machine"
    elif state == MONKEY_STATE_DISPATCHING_MACHINE:
        return "Creating Machine"
    elif state == MONKEY_STATE_DISPATCHING_INSTALLS:
        return "Installing Dependencies"
    elif state == MONKEY_STATE_DISPATCHING_SETUP:
        return "Installing Dependencies"
    elif state == MONKEY_STATE_RUNNING:
        return "Running"
    elif state == MONKEY_STATE_CLEANUP:
        return "Cleaning Up"
    elif state == MONKEY_STATE_FINISHED:
        return "Finished"
    else:
        return "unknown"

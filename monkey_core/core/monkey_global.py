import os

from core.monkey import Monkey

QUIET = False
QUIET_ANSIBLE = False
QUIET_PERIODIC_PRINTOUT = False
LOG_FILE = "monkey.log"
STATUS_LOG_FILE = "monkey.status"
ANSIBLE_LOG_FILE = "monkey_ansible.log"
DAEMON_THREAD_TIME = 10

file_path = os.path.dirname(os.path.abspath(__file__))
relative_monkeyfs_path = os.path.join(file_path, "../", "ansible/monkeyfs")
MONKEYFS_LOCAL_PATH = os.path.abspath(relative_monkeyfs_path)
print(f"Local monkeyfs path: {MONKEYFS_LOCAL_PATH}")

monkey = Monkey()


def get_monkey():
    global monkey
    return monkey

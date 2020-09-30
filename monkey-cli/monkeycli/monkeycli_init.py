import io
import os
import readline
import subprocess
from collections import defaultdict

from ruamel.yaml import YAML, round_trip_load
from termcolor import colored

from monkeycli.core_info import list_providers
from monkeycli.utils import Completer

comp = Completer()
# we want to treat '/' as part of a word, so override the delimiters
readline.set_completer_delims(' \t\n;')
readline.parse_and_bind("tab: complete")
readline.set_completer(comp.complete)


def run_command(cmd, timeout=4):
    print(cmd)
    p = subprocess.run(cmd, timeout=timeout, capture_output=True)
    return p.stdout.strip().decode("UTF-8")


def list_files(path="."):
    return os.listdir(path)


def list_dirs(path="."):
    return [x for x in os.listdir(path) if os.path.isdir(x)]


def valid_file(filename):
    return os.path.exists(filename)


def valid_dir(filename):
    return os.path.exists(filename) and os.path.isdir(filename)


def get_size(start_path='.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size


def query_yes_no(question, default="yes"):
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    while True:
        choice = input(question + prompt).lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            print("Please respond with 'yes' or 'no' " "(or 'y' or 'n').")


def list_options(input_text,
                 options,
                 default_response=None,
                 helptext="put a number or enter your own option"):
    options = [x for x in options if x is not None]
    default_response_pren = "({})".format(
        default_response) if default_response is not None else ""

    if len(options) <= 1:
        if len(options) == 1:
            default_response = options[0]
            default_response_pren = "({})".format(default_response)

        response = None
        while response is None:
            response = input("{} {}: ".format(
                input_text, default_response_pren)) or default_response
            if response is None:
                print(response, "received. Please input a response: ")
        return response
    else:
        response = None
        while response is None:
            print("Multiple options detected...")
            count = 1
            for option in options:
                print("{}). {}".format(count, option))
                count += 1
            response = input("{} ({}): ".format(input_text, helptext)).strip()
            print(response)
            try:
                num_response = int(response)
                response = options[num_response - 1]

            except:
                if response is None:
                    print(response, "received. Please input a response: ")
        print(response, "selected.")
        return response


def list_options_readable_tuples(
        input_text,
        options,
        last_options=[],
        default_response=None,
        helptext="put a number or enter your own option"):
    options = options + last_options
    option_dict = dict(options)
    resp = list_options(input_text, [x[0] for x in options], default_response,
                        helptext)
    if resp in option_dict:
        return option_dict[resp]
    return resp


def get_name():
    top_dir = run_command(["git", "rev-parse", "--show-toplevel"])
    default_name = None
    if top_dir is not None:
        default_name = run_command(["basename", top_dir])

    name = list_options("Project Name", [default_name])

    if name == "" or name is None:
        print("Invalid name: '{}'".format(name))
        return get_name()
    return name


def get_environment():
    files = [
        x for x in list_files() if "req" in x.lower() or "envi" in x.lower()
        or "dockerfile" in x.lower()
    ]
    file_map = defaultdict(list)
    valid_env_types = ["conda", "docker", "pip"]
    for f in files:
        if "req" in f.lower():
            file_map["pip"].append(f)
        elif "envi" in f.lower():
            file_map["conda"].append(f)
        elif "dockerfile" in f.lower():
            file_map["docker"].append(f)

    env_type = None
    while env_type not in valid_env_types:
        print("Please input your environment manager. Valid options: ({})".
              format(", ".join(valid_env_types)))
        env_type = list_options("Environment Type",
                                sorted(list(file_map.keys())))

    default_options = file_map[env_type] if env_type in file_map else []
    env_file = None
    env_ignore = []
    if env_type == "docker":
        return env_type, env_file, env_ignore
    while env_file is None or not valid_file(env_file):
        env_file = list_options("Environment File", default_options)

    all_dirs = list_dirs()
    for dir_name in all_dirs:
        if "bin" in list_files(dir_name) and query_yes_no(
                "Is '{}' the path of your environment directory?".format(
                    dir_name), "yes"):
            env_ignore.append(dir_name)

    return env_type, env_file, env_ignore


def get_dataset(dir_ignore):
    all_dirs = list_dirs()
    dir_sizes = sorted([(get_size(x) / (1024 * 1024), x)
                        for x in all_dirs if x not in dir_ignore],
                       reverse=True)
    dir_sizes = [x for x in dir_sizes if x[0] > 3]
    dir_sizes = [("{} {:.1f}MB".format(dirname, size), dirname)
                 for size, dirname in dir_sizes]

    while True:
        print(
            "Please choose a folder for your dataset (if there is one). \nA dataset has a checksum before copying to save time on network transfer and storage."
        )
        dataset_response = list_options_readable_tuples(
            "Dataset Folder", dir_sizes, [("None", None)])
        if dataset_response is None or valid_dir(dataset_response):
            return dataset_response


def get_persisted_folders(dir_ignore):
    all_dirs = list_dirs()
    dirs_available = sorted([x for x in all_dirs if x not in dir_ignore],
                            reverse=True)
    dirs_available.append("None/Continue")
    persisted_folders = []
    while True:
        print(
            "Please choose any folders you would like persisted. \nMake sure your code outputs to that folder and can continue execution with the data in that folder."
        )
        if len(persisted_folders) > 0:
            print("Selected folders: {}".format(", ".join(persisted_folders)))
        persisted_response = list_options("Persisted Folder(s)",
                                          dirs_available)
        if persisted_response == "None/Continue":
            break
        elif valid_dir(persisted_response):
            persisted_folders.append(persisted_response)
            if persisted_response in dirs_available:
                dirs_available.remove(persisted_response)
    return persisted_folders


def get_provider_gcp(name):
    details = round_trip_load(str({
        "name": name,
    }))
    details.fa.set_block_style()
    details.yaml_set_start_comment("\nGCP Provider: {}".format(name))

    return details


def get_provider_aws(name):
    details = round_trip_load(str({
        "name": name,
    }))
    details.fa.set_block_style()
    details.yaml_set_start_comment("\nAWS Provider: {}".format(name))
    machine_type = None
    while machine_type is None:
        gpu_instance = query_yes_no("Do you need GPUs in your instances?",
                                    "yes")
        if gpu_instance:
            options = [
                ("1 gpus \t(p3.2xlarge, \t8 cpu)", "p3.2xlarge"),
                ("4 gpus \t(p3.8xlarge, \t32 cpu)", "p3.8xlarge"),
                ("8 gpus \t(p3.16xlarge, \t64 cpu)", "p3.16xlarge"),
                ("8 gpus \t(p3.24xlarge, \t96 cpu)", "p3.24xlarge"),
                ("1 gpus \t(p2.xlarge, \t4 cpu)", "p2.xlarge"),
                ("8 gpus \t(p2.8xlarge, \t32 cpu)", "p2.8xlarge"),
                ("16 gpus \t(p2.16xlarge, \t64 cpu)", "p2.16xlarge"),
            ]
            machine_type = list_options_readable_tuples(
                "Machine Type",
                options,
                helptext="Pick a number or enter your own machine type string")
        else:
            option_categories = [
                ("Compute Optimized", "compute"),
                ("Memory Optimized", "memory"),
                ("Storage Optimized", "storage"),
                ("Custom", "custom"),
            ]
            category = list_options_readable_tuples("Machine Category",
                                                    option_categories)
            if category == "compute":
                print("Compute category picked")
                options = [
                    ("1 cpus \t(c6g.medium, \t2GB)","c6g.medium"),
                    ("2 cpus (c6g.large, \t4GB)","c6g.large"),
c6g.xlarge	4	8	EBS-Only	Up to 10	Up to 4,750
c6g.2xlarge	8	16	EBS-Only	Up to 10	Up to 4,750
c6g.4xlarge	16	32	EBS-Only	Up to 10	4750
c6g.8xlarge	32	64	EBS-Only	12	9000
c6g.12xlarge	48	96	EBS-Only	20	13500
c6g.16xlarge	64	128	EBS-Only	25	19000
c6g.metal	64	128	EBS-Only	25	19000
c6gd.medium	1	2	1 x 59 NVMe SSD	Up to 10	Up to 4,750
c6gd.large	2	4	1 x 118 NVMe SSD	Up to 10	Up to 4,750
c6gd.xlarge	4	8	1 x 237 NVMe SSD	Up to 10	Up to 4,750
c6gd.2xlarge	8	16	1 x 474 NVMe SSD	Up to 10	Up to 4,750
c6gd.4xlarge	16	32	1 x 950 NVMe SSD	Up to 10	4,750
c6gd.8xlarge	32	64	1 x 1900 NVMe SSD	12	9,000
c6gd.12xlarge	48	96	2 x 1425 NVMe SSD	20	13,500
c6gd.16xlarge	64	128	2 x 1900 NVMe SSD	25	19,000
c6gd.metal	64	128	
                ]
            elif category == "memory":
                print("Memory category picked")
            elif category == "storage":
                print("Storage category picked")
            else:
                print("Custom category picked")

            pass

    return details


def get_provider_setup():
    providers = []
    core_providers = list_providers()
    core_provider_text = [
        ("Name: {}, Type: {}".format(colored(x["name"], "green"),
                                     colored(x["type"],
                                             "green")), (x["name"], x["type"]))
        for x in core_providers
    ]

    while True:
        print(
            "Monkey Core currently has these providers available: \n{}".format(
                ", ".join([
                    "({}, type: {})".format(x[1][0], x[1][1])
                    for x in core_provider_text
                ])))

        print(
            "\nPlease choose the providers you would like to dispatch your job to."
        )
        if len(providers) == 0:
            print("The first provider chosen will be the default provider")

        provider_response = list_options_readable_tuples(
            "Providers", core_provider_text, [("Continue", None)])
        if provider_response is None:
            break

        if type(provider_response) is not tuple or len(provider_response) != 2:
            print("Invalid response, please select an available response")
            continue

        provider_name, provider_type = provider_response
        if provider_type == "aws":
            new_provider_info = get_provider_aws(provider_name)
            if new_provider_info is not None:
                print("Successfully added", provider_name)
                providers.append(new_provider_info)
                try:
                    core_provider_text.remove(provider_response)
                except:
                    pass
        elif provider_type == "gcp":
            new_provider_info = get_provider_gcp(provider_name)
            if new_provider_info is not None:
                print("Successfully added", provider_name)
                providers.append(new_provider_info)
                try:
                    core_provider_text.remove(provider_response)
                except:
                    pass

    return providers


def init_runfile():
    print("Initiating default run.yml")
    # project_name = get_name()
    # print("")
    # env_type, env_file, env_ignore = get_environment()
    # print("")
    # dataset = get_dataset(env_ignore)
    # print("")
    # persisted_folders = get_persisted_folders(env_ignore + [dataset])
    # print("")

    providers = get_provider_setup()
    print(providers)
    print("")

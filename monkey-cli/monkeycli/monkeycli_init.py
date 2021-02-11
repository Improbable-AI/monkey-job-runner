import io
import os
import re
import readline
import subprocess
from collections import defaultdict

from ruamel.yaml import YAML, round_trip_load
from termcolor import colored

import monkeycli.aws_instance_types
from monkeycli.core_info import list_providers
from monkeycli.utils import Completer

comp = Completer()
# we want to treat '/' as part of a word, so override the delimiters
readline.set_completer_delims(' \t\n;')
readline.parse_and_bind("tab: complete")
readline.set_completer(comp.complete)


def run_command(cmd, timeout=4):
    p = subprocess.run(cmd, timeout=timeout, capture_output=True)
    return p.stdout.strip().decode("UTF-8")


def remove_colors(text):
    reaesc = re.compile(r'\x1b[^m]*m')
    return reaesc.sub('', text)


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
            print("Multiple options detected...\n")
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
    default_workflow_name = os.path.basename(os.getcwd())
    if top_dir is not None:
        default_name = run_command(["basename", top_dir])

    project_name = None
    workflow_name = None

    while project_name == "" or project_name is None:
        project_name = list_options("Project Name", [default_name])

    while workflow_name == "" or workflow_name is None:
        workflow_name = list_options("Workflow Name", [default_workflow_name])

    return project_name, workflow_name


def get_environment():
    files = [
        x for x in list_files() if "req" in x.lower() or "envi" in x.lower()
        or "dockerfile" in x.lower()
    ]
    file_map = defaultdict(list)
    valid_env_types = ["conda", "docker", "pip", "none"]
    for f in files:
        if "req" in f.lower():
            file_map["pip"].append(f)
        elif "envi" in f.lower():
            file_map["conda"].append(f)
        elif "dockerfile" in f.lower():
            file_map["docker"].append(f)

    env_type = None
    while env_type not in valid_env_types:
        print("Please input your environment manager.")
        # print("Please input your environment manager. Valid options: ({})".
        #       format(", ".join(valid_env_types)))
        env_type = list_options_readable_tuples("Environment Type",
                                                [(x.capitalize(), x)
                                                 for x in valid_env_types])
        # env_type = list_options("Environment Type",
        #                         sorted(list(file_map.keys())))

    default_options = file_map[env_type] if env_type in file_map else []
    env_file = None
    env_ignore = []
    if env_type == "docker":
        return env_type, env_file, env_ignore
    while env_file is None or not valid_file(env_file):
        print("")
        env_file = list_options("Environment File", default_options)

    all_dirs = list_dirs()
    for dir_name in all_dirs:
        if "bin" in list_files(dir_name) and query_yes_no(
                "Is '{}' the path of your environment directory?".format(
                    dir_name), "yes"):
            env_ignore.append(dir_name)

    return env_type, env_file, env_ignore


def get_installs(env_type):
    if env_type in ("conda", "pip"):
        return [env_type]
    if env_type == "docker":
        return ["nvidia-docker"]


def get_dataset(dir_ignore):
    all_dirs = list_dirs()
    dir_sizes = sorted([(get_size(x) / (1024 * 1024), x)
                        for x in all_dirs if x not in dir_ignore],
                       reverse=True)
    dir_sizes = [x for x in dir_sizes if x[0] > 3]
    dir_sizes = [("{} {:.1f}MB".format(dirname, size), dirname)
                 for size, dirname in dir_sizes]

    dataset_folders = []

    while True:
        print(
            "Please choose a folder for your dataset (if there is one). \nA dataset has a checksum before copying to save time on network transfer and storage."
        )
        if len(dataset_folders) > 0:
            print("Selected folders: {}\n".format(", ".join(dataset_folders)))

            dataset_response = list_options_readable_tuples(
                "Dataset Folder(s)", dir_sizes, [("Continue", None)])
        else:
            dataset_response = list_options_readable_tuples(
                "Dataset Folder(s)", dir_sizes, [("None/Continue", None)])
        if dataset_response is None:
            break
        elif valid_dir(dataset_response):
            dataset_folders.append(dataset_response)

            remove_option = None
            for readable_dirname, dirname in dir_sizes:
                if dirname == dataset_response:
                    remove_option = (readable_dirname, dirname)
            if remove_option is not None and remove_option in dir_sizes:
                dir_sizes.remove(remove_option)
    return dataset_folders


def get_persisted_folders(dir_ignore):
    all_dirs = list_dirs()
    dirs_available = sorted([(x, x) for x in all_dirs if x not in dir_ignore],
                            reverse=True)
    persisted_folders = []
    while True:
        print(
            "\nPlease choose any folders you would like persisted. \nMake sure your code outputs to that folder and can continue execution with the data in that folder."
        )
        if len(persisted_folders) > 0:
            print("Selected folders: {}\n".format(
                ", ".join(persisted_folders)))

            persisted_response = list_options_readable_tuples(
                "Persisted Folder(s)", dirs_available, [("Continue", None)])
        else:
            persisted_response = list_options_readable_tuples(
                "Persisted Folder(s)", dirs_available,
                [("None/Continue", None)])
        if persisted_response is None:
            break
        elif valid_dir(persisted_response):
            persisted_folders.append(persisted_response)
            if (persisted_response, persisted_response) in dirs_available:
                dirs_available.remove((persisted_response, persisted_response))
    return persisted_folders


def get_provider_local(name):
    details = round_trip_load(str({
        "name": name,
    }))
    details.fa.set_block_style()
    details.yaml_set_start_comment("\nLocal Provider: {}".format(name))

    return details


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
    while machine_type is None or monkeycli.aws_instance_types.aws_valid_type(
            machine_type) == False:
        gpu_instance = query_yes_no("Do you need GPUs in your instances?",
                                    "yes")
        if gpu_instance:

            options = [
                ("{: >2} gpus, {: >3} cpus ({: >15} | {: >8} | ${:.2f}/h)".
                 format(x.gpus, x.cpus, x.name, x.memory,
                        x.price_float), x.name)
                for x in monkeycli.aws_instance_types.get_gpu_instances()
            ]
            machine_type = list_options_readable_tuples(
                "Machine Type",
                options,
                helptext="Pick a number or enter your own machine type string")
        else:
            option_categories = [
                ("Compute Optimized", "compute"),
                ("Memory Optimized", "memory"),
                ("General", "general"),
                # ("Custom", "custom"),
            ]
            category = list_options_readable_tuples("Machine Category",
                                                    option_categories)

            def pick_instances(minimal_f, all_f):
                options = [
                    ("{: >3} cpus ({: >15} | {: >8} | ${:.2f}/h)".format(
                        x.cpus, x.name, x.memory, x.price_float), x.name)
                    for x in minimal_f()
                ]
                machine_type = list_options_readable_tuples(
                    "Machine Type",
                    options, [("More options", "more")],
                    helptext=
                    "Pick a number or enter your own machine type string")

                if machine_type == "more":
                    options = [
                        ("{: >3} cpus ({: >15} | {: >8} | ${:.2f}/h)".format(
                            x.cpus, x.name, x.memory, x.price_float), x.name)
                        for x in all_f()
                    ]
                    machine_type = list_options_readable_tuples(
                        "Machine Type",
                        options,
                        helptext=
                        "Pick a number or enter your own machine type string")
                return machine_type

            if category == "compute":
                print("Compute category picked")
                machine_type = pick_instances(
                    monkeycli.aws_instance_types.get_minimal_compute_instances,
                    monkeycli.aws_instance_types.get_compute_instances)

            elif category == "memory":
                print("Memory category picked")
                machine_type = pick_instances(
                    monkeycli.aws_instance_types.get_minimal_memory_instances,
                    monkeycli.aws_instance_types.get_memory_instances)
            elif category == "general":
                print("General category picked")
                machine_type = pick_instances(
                    monkeycli.aws_instance_types.get_minimal_general_instances,
                    monkeycli.aws_instance_types.get_general_instances)
            else:
                print("Custom category picked")
            if monkeycli.aws_instance_types.aws_valid_type(
                    machine_type) == False:
                print("Invalid type...  Trying again...\n")

    details["machine_type"] = machine_type
    details.yaml_set_comment_before_after_key(
        "machine_type",
        before=
        "Pick an AWS instance type (https://aws.amazon.com/ec2/instance-types/)"
    )

    disk_size = None
    while disk_size is None or type(disk_size) != int:
        print("\nHow much space would you need in each machine (GB)?")
        disk_size = list_options_readable_tuples("Disk Size", [("10GB", "10")])
        try:
            disk_size = int(disk_size)
        except:
            print("Could not parse int from disk size GB")
    print("Selected {}GB".format(disk_size))

    details["disk_size"] = disk_size
    details.yaml_set_comment_before_after_key("disk_size",
                                              before="Disk Size (GB)")
    details["disk_type"] = "gp2"
    # details.yaml_add_eol_comment("General purpose SSD", "disk_type")
    details.yaml_set_comment_before_after_key(
        "disk_type",
        before=
        "Available disk types (gp2, st1) (https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-volume-types.html)"
    )

    source_image = None
    while source_image is None or source_image == "":
        print(
            "\nPlease pick a base image (20.04 is most supported).\nPlease make sure the image type is compatible with the machine type {}"
            .format(machine_type))
        detected_architecture = monkeycli.aws_instance_types.get_machine_type_architecture(
            machine_type)
        print("\nYour machine type {} is detected to be: {}\n".format(
            machine_type, colored(detected_architecture, "green")))

        color_matching_x86 = colored(
            "x86", "green") if "x86" == detected_architecture else "x86"
        color_matching_ARM = colored(
            "ARM", "green") if "ARM" == detected_architecture else "ARM"

        options = [
            ("Deep Learning Ubuntu 18.04 {} ( ami-01aad86525617098d )".format(
                color_matching_x86), "ami-01aad86525617098d"),
            ("Ubuntu 20.04 {} ( ami-0dba2cb6798deb6d8 )".format(
                color_matching_x86), "ami-0dba2cb6798deb6d8"),
            ("Ubuntu 20.04 {} ( ami-0dba2cb6798deb6d8 )".format(
                color_matching_x86), "ami-0dba2cb6798deb6d8"),
            ("Ubuntu 20.04 {} ( ami-0ea142bd244023692 )".format(
                color_matching_ARM), "ami-0ea142bd244023692"),
            ("Ubuntu 18.04 {} ( ami-0817d428a6fb68645 )".format(
                color_matching_x86), "ami-0817d428a6fb68645"),
            ("Ubuntu 18.04 {} ( ami-0f2b111fdc1647918 )".format(
                color_matching_ARM), "ami-0f2b111fdc1647918")
        ]
        source_image = list_options_readable_tuples(
            "Source image",
            options,
            helptext="Pick one or put the ami for your own custom image")
        for read, key in options:
            if source_image == key:
                base_image_str = remove_colors(read)

    details["base_image"] = source_image
    details.yaml_set_comment_before_after_key(
        "base_image",
        before="Currently only Ubuntu 18.04/20.04 is supported. {}".format(
            "\n" + base_image_str if base_image_str is not None else ""))

    spot = None
    spot_price = None
    while spot is None:
        spot = query_yes_no(
            "Would you like your instance to be a Spot instance?", "yes")
        instance_info = monkeycli.aws_instance_types.get_instance_info(
            machine_type)
        print("Current price of a {}: {:.3f}$/hr".format(
            instance_info.name, instance_info.price_float))
        if spot:
            spot_price = instance_info.price_float
        # if spot:
        #     print(
        #         "How much of a discount are you looking for?\nBidding will only run under the price specified"
        #     )

        #     instance_info = monkeycli.aws_instance_types.get_instance_info(
        #         machine_type)
        #     print("Current price of a {}: {:.3f}$/hr".format(
        #         instance_info.name, instance_info.price_float))
        #     discounts = [20, 40, 60, 70]
        #     options = []
        #     for disc in discounts:
        #         price = instance_info.price_float * (100 - disc) / 100
        #         readable = "{}%  ${:.2f}/hr -> ${:.3f}/hr".format(
        #             disc, instance_info.price_float, price)
        #         options.append((readable, price))

        #     spot_price = -1
        #     spot_price_readable = None
        #     while spot_price == -1:
        #         spot_price = list_options_readable_tuples(
        #             "Spot Price",
        #             options, [("Skip", None)],
        #             helptext="Put a number or enter your own price")
        #         if spot_price is not None:
        #             try:
        #                 for readable, val in options:
        #                     if val == spot_price:
        #                         spot_price_readable = readable
        #                 spot_price = float(spot_price)

        #                 if spot_price_readable is None:

        #                     spot_price_readable = "{:.0f}%  ${:.3f}/hr -> ${:.3f}/hr".format(
        #                         (instance_info.price_float - spot_price) /
        #                         instance_info.price_float * 100,
        #                         instance_info.price_float, spot_price)
        #                     print(spot_price_readable)
        #             except Exception as e:
        #                 print(e)
        #                 spot_price = -1

    details["spot"] = spot
    details["spot_price"] = spot_price
    details.yaml_set_comment_before_after_key(
        "spot_price",
        before=
        "This is the maximum bid price you are willing to give for the machine. "
    )
    # if spot_price_readable is not None:
    #     details.yaml_set_comment_before_after_key("spot_price",
    #                                               before=spot_price_readable)

    return details


def get_provider_setup():
    providers = []
    try:
        core_providers = list_providers()
    except:
        print(
            "Unable to connect to Monkey Core.  Please make sure core is started then retry"
        )
        raise ValueError("Unable to connect to Monkey Core")
    if core_providers == []:
        raise ValueError("Unable to connect to Monkey Core")
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
        else:
            print("Add additional providers if available")

        provider_response = list_options_readable_tuples(
            "Providers", core_provider_text, [("Continue", None)])
        if provider_response is None:
            break

        if type(provider_response) is not tuple or len(provider_response) != 2:
            print("Invalid response, please select an available response")
            continue

        provider_name, provider_type = provider_response
        attempt_removal = False
        if provider_type == "aws":
            new_provider_info = get_provider_aws(provider_name)
            if new_provider_info is not None:
                print("Successfully added", provider_name)
                providers.append(new_provider_info)
                attempt_removal = True
        elif provider_type == "gcp":
            new_provider_info = get_provider_gcp(provider_name)
            if new_provider_info is not None:
                print("Successfully added", provider_name)
                providers.append(new_provider_info)
                attempt_removal = True
        elif provider_type == "local":
            print("Setting up local provider")
            new_provider_info = get_provider_local(provider_name)
            if new_provider_info is not None:
                print("Successfully added", provider_name)
                providers.append(new_provider_info)
                attempt_removal = True

        if attempt_removal:
            try:
                removal = None
                for text, pr in core_provider_text:
                    if pr == provider_response:
                        removal = (text, pr)
                if removal is not None:
                    core_provider_text.remove(removal)
            except:
                pass
    return providers


def runfile_write(project_name, workflow_name, env_type, env_file, env_ignore,
                  installs, dataset, persisted_folders, providers):

    full_file = round_trip_load(
        str({
            "name": workflow_name,
            "project_name": project_name,
        }))
    full_file.fa.set_block_style()

    #######
    # Run Section
    #######
    run_yml = round_trip_load(str({
        "env_type": env_type,
        "env_file": env_file
    }))
    run_yml.fa.set_block_style()
    run_yml.yaml_set_comment_before_after_key(
        "env_type", before="Supported env_type options: conda, pip, docker")
    run_yml.yaml_set_comment_before_after_key(
        "env_file",
        before=
        "Please set it to the requirements.txt file or environment.yml file")
    full_file["run"] = run_yml

    run_yml.fa.set_block_style()

    #######
    # Install Section
    #######
    install_yml = round_trip_load(str(installs))
    install_yml.fa.set_block_style()
    install_yml.yaml_set_start_comment(
        "Installs each of the system dependencies.\nCurrent available options include: docker, cuda10.2,\n"
    )
    full_file["install"] = install_yml

    #######
    # Code Section
    #######
    code_yml = round_trip_load(str({"path": "."}))
    code_yml.fa.set_block_style()
    code_yml["ignore"] = env_ignore + dataset + persisted_folders
    code_yml.yaml_set_comment_before_after_key(
        "ignore",
        before=
        "When packing up the codebase, monkey will ignore the following paths")
    code_yml.yaml_set_start_comment("Defines the codebase path")

    full_file["code"] = code_yml

    #######
    # Persist Section
    #######
    persist_yml = round_trip_load(str([]))
    persist_yml.fa.set_block_style()
    persist_yml += persisted_folders
    persist_yml.yaml_set_start_comment("""
Define folders or files to persist throughout runs.
Should include your output or checkpoint directory
Any defined persist folder will be kept in persistent storage and applied over the codebase at start
Persisted folders will be unpacked in the order they are listed
    """)
    full_file["persist"] = persist_yml

    #######
    # Data Section
    #######
    data_yml = round_trip_load(str([]))
    data_yml.fa.set_block_style()
    count = 0
    for ds in dataset:
        inner_yml = round_trip_load(
            str({
                "name": project_name + "-data-{}".format(count),
                "type": "copy",
                "path": ds,
                "compression": "gztar"
            }))
        inner_yml.fa.set_block_style()
        if count == 0:
            inner_yml.yaml_set_comment_before_after_key("type",
                                                        before="""
Dataset type options are fore copy or mount.  Mount will directly mount the dataset bucket while copy will copy the dataset to local memory (highly recommended and only supported)
            """)
            inner_yml.yaml_set_comment_before_after_key("path",
                                                        before="""
Path should be a relative directory that will only be reuploaded if a checksum does not match
            """)
            inner_yml.yaml_set_comment_before_after_key("compression",
                                                        before="""
optional compression type. (Must have compression packages available on machine)  Options: tar, gztar (default)
            """)
        count += 1
        data_yml.append(inner_yml)
    full_file["data"] = data_yml
    full_file.yaml_set_comment_before_after_key("data",
                                                before="""
Dataset folders will be checksummed before re-uploading
    """)

    #######
    # Providers Section
    #######
    full_file["providers"] = providers

    # Check for existing job.yml
    if os.path.isfile("job.yml"):
        count = 0
        while os.path.isfile("job.yml.old.{}".format(count)):
            count += 1
        new_file = "job.yml.old.{}".format(count)
        print(
            "\nRenaming existing job.yml file\njob.yml -> {}".format(new_file))
        os.rename("job.yml", new_file)

    print("\nWriting job.yml file...\n")
    with open("job.yml", "w") as f:
        y = YAML()
        y.explicit_start = True
        y.indent(mapping=4, sequence=4, offset=2)
        y.default_flow_style = False
        y.dump(full_file, f)


def init_runfile():
    print("\n\nInitiating default run.yml\n")
    project_name, workflow_name = get_name()
    print("")
    env_type, env_file, env_ignore = get_environment()
    print("")

    installs = get_installs(env_type)

    print("")
    dataset = get_dataset(env_ignore)
    print("")
    persisted_folders = get_persisted_folders(env_ignore + dataset)
    print("")

    providers = get_provider_setup()
    print("")

    runfile_write(project_name, workflow_name, env_type, env_file, env_ignore,
                  installs, dataset, persisted_folders, providers)

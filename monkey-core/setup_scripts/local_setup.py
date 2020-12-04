import getpass
import os
import random
import readline
import string
import subprocess
from collections import OrderedDict

import ansible_runner
import yaml
from core.monkey_provider_local import MonkeyProviderLocal
from ruamel.yaml import YAML, round_trip_load
from ruamel.yaml.comments import CommentedMap

from setup_scripts.utils import (Completer, check_for_existing_local_command,
                                 printout_ansible_events)

comp = Completer()
# we want to treat '/' as part of a word, so override the delimiters
readline.set_completer_delims(' \t\n;')
readline.parse_and_bind("tab: complete")
readline.set_completer(comp.complete)


def check_local_provider(yaml):
    provider_name = yaml.get("name")
    print("Checking integrity of", provider_name, "with type:",
          yaml.get("type"))

    runner = ansible_runner.run(playbook='local_setup_checks.yml',
                                private_data_dir='ansible',
                                quiet=True)
    events = [e for e in runner.events]
    if runner.status == "failed":
        printout_ansible_events(events)

        print("Failed to mount the AWS S3 filesystem")
        return False
    print("Mount successful")

    return True


def create_local_provider(provider_name, yaml, args):
    details = round_trip_load(str({
        "name": provider_name,
        "type": "local",
    }))
    details.fa.set_block_style()
    details.yaml_set_start_comment(
        "\nLocal Provider: {}".format(provider_name))

    monkeyfs_path = os.path.join(os.getcwd(), f"ansible/monkeyfs")

    # Create filesystem bucket and pick a new id if failed
    details["local_monkeyfs_path"] = monkeyfs_path

    details["monkeyfs_path"] = input(
        "Set remote filesystem mount path (~/monkeyfs): ") or "~/monkeyfs"
    details.yaml_add_eol_comment("Defaults to ~/monkeyfs", "monkeyfs_path")

    details["monkey_scratch"] = input(
        "Set remote scratch (~/monkey-scratch): ") or "~/monkey-scratch"
    details.yaml_add_eol_comment("Defaults to ~/monkey-scratch",
                                 "monkey_scratch")

    cmd = 'ifconfig | grep -B 8 -e "packets [^0]" | grep "inet .* broadcast"'
    p = subprocess.run(cmd, shell=True, check=True, capture_output=True)
    output = [x.strip() for x in p.stdout.decode("utf-8").split("\n")]
    ip_found = ""
    if len(output):
        output = [x for x in output[0].split(" ")]
        if len(output) >= 2 and output[0] == 'inet':
            ip_found = output[1]
    else:
        output = ""
    details["monkeyfs_public_ip"] = input(
        f"SSHable IP from remote computers ({ip_found}): ") or ip_found
    details["monkeyfs_public_port"] = input(f"SSH port (22): ") or "22"
    details["monkeyfs_public_user"] = ""
    details.yaml_add_eol_comment("Defaults to ~/monkey-scratch",
                                 "monkey_scratch")
    local_instance_details_file = input(
        f"Set a file for local instance details (local.yml): ") or f"local.yml"
    details["local_instance_details"] = local_instance_details_file
    details.yaml_add_eol_comment(f"Defaults to local.yml",
                                 "local_instance_details")

    providers = yaml.get("providers", [])
    if providers is None:
        providers = []
    providers.append(details)
    yaml["providers"] = providers

    print("\nWriting to providers.yml...")
    with open('providers.yml', 'w') as file:
        y = YAML()
        yaml.fa.set_block_style()
        y.explicit_start = True
        y.default_flow_style = False
        y.dump(yaml, file)

    print("\nWriting local vars file...")
    local_vars = round_trip_load(
        str({
            "monkeyfs_path": details["monkeyfs_path"],
            "monkey_scratch": details["monkey_scratch"],
            "local_monkeyfs_path": monkeyfs_path,
            "local_instance_details": details["local_instance_details"],
            "monkeyfs_public_ip": details["monkeyfs_public_ip"],
            "monkeyfs_public_port": details["monkeyfs_public_port"],
            "monkeyfs_user": getpass.getuser(),
        }))
    write_vars_file(local_vars)
    create_local_monkeyfs()

    instance_details_yaml = YAML()
    existing_hosts = OrderedDict()
    try:
        with open(local_instance_details_file) as f:
            instance_details_yaml = YAML().load(f)
            existing_hosts = instance_details_yaml.get("hosts", OrderedDict())
    except:
        print("No providers.yml file found")
        instance_details_yaml = CommentedMap()

    print(f"{len(existing_hosts)} existing hosts found")

    local_provider = MonkeyProviderLocal(details)
    for host in existing_hosts:
        print(f"Checking integrity for host: {host}")
        instance = local_provider.create_local_instance(name=host,
                                                        hostname=host)
        if instance is None:
            print(f"FAILED: to create instance {host}")

    # Check inventory file for non existing hosts
    try:
        with open("ansible/inventory/local/inventory.local.yml") as f:
            inv_yaml = YAML(typ='safe', pure=True)
            inventory_yaml = inv_yaml.load(f)
    except:
        inventory_yaml = round_trip_load("---")

    def walk_inventory(prev_key, inv):
        results = OrderedDict()
        for key, val in inv.items():
            if type(val) is dict:
                if key != "hosts":
                    results.update(walk_inventory(key, val))
                else:
                    host_keys = list(val.keys())
                    for new_host in host_keys:
                        new_host_dict = {
                            new_host: {
                                "status":
                                "init",
                                "main_group":
                                prev_key,
                                "monkeyfs_public_ip":
                                details["monkeyfs_public_ip"],
                                "monkeyfs_public_port":
                                details["monkeyfs_public_port"],
                            }
                        }
                        results.update(new_host_dict)
        return results

    inv_hosts = walk_inventory("all", inventory_yaml)

    def write_instance_details(instance_details, hosts):
        instance_details["hosts"] = hosts
        with open(local_instance_details_file, "w") as f:
            y = YAML()
            instance_details.fa.set_block_style()
            y.explicit_start = True
            y.default_flow_style = False
            y.dump(instance_details, f)
            print("Writing local instance details to: ",
                  local_instance_details_file)

    for key, val in inv_hosts.items():
        done = 0
        while done == 0 and (key not in existing_hosts
                             or existing_hosts[key]["status"] == "init"):
            inpt = None
            while inpt is None:
                inpt = input(
                    f"'{key}', not found in local provider.  \nAdd it? (Y/n/s) (Yes/no/skip all): "
                )
                if inpt == "":
                    inpt = "y"
                inpt = inpt[0].lower()
                if inpt not in ["y", "n", "s"]:
                    inpt = None
            if inpt == "y":
                print(f"Adding {key}...\n")
                existing_hosts[key] = val
                write_instance_details(instance_details_yaml, existing_hosts)
                print(f"Creating instance {key}...\n")

                def failed_instance_creation(existing_hosts, key):
                    try:
                        default_ip = existing_hosts[key]["monkeyfs_public_ip"]
                        default_port = existing_hosts[key][
                            "monkeyfs_public_port"]
                        alt_public_ip = input(
                            "\nTry an alternative public ip address?" +
                            f"\n(ctrl-c to skip host) (default: {default_ip}): "
                        ) or default_ip
                        print(
                            f"Setting public ip for {key} to {alt_public_ip}")
                        alt_public_port = input(
                            f"\nTry an alternative public port? ({default_port}) : "
                        ) or default_port
                        print(
                            f"Setting the port for {key} to {alt_public_port}")

                        existing_hosts[key][
                            "monkeyfs_public_ip"] = alt_public_ip
                        existing_hosts[key][
                            "monkeyfs_public_port"] = alt_public_port
                        return 0
                    except KeyboardInterrupt as e:
                        print(
                            f"\n\nKeyboard interrupt detected...\nSkipping {key}"
                        )
                        print(f"Failed to add {key}: \n{e}")
                        if key in existing_hosts:
                            del existing_hosts[key]
                        return 1

                try:
                    instance = local_provider.create_local_instance(
                        name=key, hostname=key)
                    print(instance)
                    if instance is None:
                        print(f"failed to create instance {key}")
                        done = failed_instance_creation(existing_hosts, key)
                    else:
                        existing_hosts[key]["status"] = "unknown"
                        done = 1
                except KeyboardInterrupt as e:
                    print(
                        f"\n\nKeyboard interrupt detected...\nSkipping {key}")
                    print(f"Failed to add {key}: \n{e}")
                    del existing_hosts[key]
                    done = 1
                    continue
                except Exception as e:
                    print(f"Failed to add {key}: \n{e}")
                    done = failed_instance_creation(existing_hosts, key)
                    continue
            elif inpt == "n":
                print(f"Not adding {key}...\n")
                done = 1
            elif inpt == "s":
                print("Skipping all further prompts")
                done = 2
                break
        if done == 2:
            break

    # local_inventory = round_trip_load(
    #     str({
    #         "aws_access_key": cred_environment["AWS_ACCESS_KEY_ID"],
    #         "aws_secret_key": cred_environment["AWS_SECRET_ACCESS_KEY"],
    #         "plugin": "aws_ec2",
    #         "regions": [region_input],
    #         "groups": {
    #             "monkey": "'monkey' in tags.Name",
    #             "monkey_aws": "'monkey' in tags.Name",
    #         },
    #         "hostnames": ["tag:Name"],
    #         "filters": {
    #             "tag:Monkey": "Monkey_AWS"
    #         },
    #         "compose": {
    #             "ansible_host": "public_ip_address",
    #         }
    #     }))
    # aws_inventory.fa.set_block_style()
    # write_inventory_file(aws_inventory)


def create_local_monkeyfs():
    print("\nSetting up monkeyfs...")

    runner = ansible_runner.run(playbook='local_setup_create.yml',
                                private_data_dir='ansible',
                                quiet=False)

    if runner.status == "failed":
        print("Failed installing and setting up monkeyfs")
        return False
    print("Successfully created local provider")
    return True


def write_commented_file(file, yaml_items):
    yaml_items.fa.set_block_style()
    with open(file, "w") as file:
        try:
            y = YAML()
            y.explicit_start = True
            y.default_flow_style = False
            y.dump(yaml_items, file)
        except:
            print("Failed to write aws file: ", file)
            exit(1)


def write_inventory_file(local_inventory):
    ansible_local_file = "ansible/inventory/aws/inventory.compute.aws_ec2.yml"
    write_commented_file(ansible_local_file, local_inventory)


def write_vars_file(local_vars):
    local_vars_file = "ansible/local_vars.yml"
    write_commented_file(local_vars_file, local_vars)

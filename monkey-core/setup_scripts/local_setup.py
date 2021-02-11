import getpass
import os
import readline
import subprocess
import sys
from collections import OrderedDict

import ansible_runner
from core.monkey_provider_local import MonkeyProviderLocal
from ruamel.yaml import YAML, round_trip_load
from ruamel.yaml.comments import CommentedMap

from setup_scripts.utils import Completer, printout_ansible_events

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


def scan_for_local_ip():
    cmd = 'ifconfig | grep -B 8 -e "packets [^0]" | grep -e UP -e packets -e "inet "'
    p = subprocess.run(cmd, shell=True, check=True, capture_output=True)
    output = [x.strip() for x in p.stdout.decode("utf-8").split("\n")]
    interfaces = [(x.split(":")[0], output.index(x)) for x in output
                  if "UP" in x]
    res = []
    for _, index in interfaces:
        if index < len(output) + 3 and "inet" in output[
                index + 1] and "packets" in output[
                    index + 2] and "packets" in output[index + 3]:
            try:
                inet = output[index + 1].split(" ")[1]
                packets = int(output[index + 2].split(" ")[2]) + int(
                    output[index + 3].split(" ")[2])
                res.append((packets, inet))
            except:
                pass
    if (res):
        return sorted(res, reverse=True)[0][1]
    return None


def write_vars_to_provider(yaml_input, local_vars):
    providers = yaml_input.get("providers", [])
    if providers is None:
        providers = []
    providers.append(local_vars)
    yaml_input["providers"] = providers

    print("\nWriting to providers.yml...")
    with open('providers.yml', 'w') as file:
        y = YAML()
        yaml_input.fa.set_block_style()
        y.explicit_start = True
        y.default_flow_style = False
        y.dump(yaml_input, file)


def generate_new_host_dict(new_host,
                           main_group="unknown",
                           monkeyfs_public_ip="unknown",
                           monkeyfs_public_port="22"):
    host_dict = {
        "status": "init",
        "main_group": main_group,
        "monkeyfs_public_ip": monkeyfs_public_ip,
        "monkeyfs_public_port": monkeyfs_public_port,
    }
    return host_dict


def walk_inventory(walk_key, local_vars, inventory_yaml):
    results = []
    for key, val in inventory_yaml.items():
        if type(val) is dict:
            if key != "hosts":
                results += walk_inventory(walk_key=key,
                                          local_vars=local_vars,
                                          inventory_yaml=val)
            else:
                results += [(x, walk_key) for x in list(val.keys())]
    return results


def write_instance_details(local_instances_file, instance_details, hosts):
    instance_details["hosts"] = hosts
    with open(local_instances_file, "w") as f:
        y = YAML()
        instance_details.fa.set_block_style()
        y.explicit_start = True
        y.default_flow_style = False
        y.dump(instance_details, f)
        print("Writing local instance details to: ", local_instances_file)


def create_local_provider(provider_name, yaml_input, args):
    monkeyfs_path = os.path.join(os.getcwd(), f"ansible/monkeyfs")
    local_monkeyfs_path = monkeyfs_path
    monkeyfs_path = args.monkeyfs_path or "~/monkeyfs"
    monkeyfs_scratch = args.monkeyfs_scratch or "~/monkey-scratch"
    monkeyfs_public_ip = args.monkeyfs_public_ip or "localhost"
    monkeyfs_public_port = args.monkeyfs_public_port or "22"
    local_instances_file = args.local_instances_file or "local.yml"
    if not args.noinput:
        if not args.monkeyfs_path:
            monkeyfs_path = input(
                f"Set remote filesystem mount path ({monkeyfs_path}): "
            ) or monkeyfs_path
        print(f"Monkeyfs mount path: {monkeyfs_path}")
        if not args.monkeyfs_scratch:
            monkeyfs_scratch = input(
                f"Set remote scratch ({monkeyfs_scratch}): "
            ) or monkeyfs_scratch
        print(f"Monkeyfs scratch path: {monkeyfs_scratch}")
        ip_found = scan_for_local_ip() or monkeyfs_public_ip
        if not args.monkeyfs_public_ip:
            monkeyfs_public_ip = input(
                f"SSHable IP from remote computers ({ip_found}): ") or ip_found
        print(f"Monkeyfs public ip: {monkeyfs_public_ip}")
        if not args.monkeyfs_public_port:
            monkeyfs_public_port = input(
                f"SSH port ({monkeyfs_public_port}): ") or monkeyfs_public_port
        print(f"Monkeyfs public port: {monkeyfs_public_port}")
        if not args.local_instances_file:
            local_instances_file = input(
                f"Set a file for local instance details ({local_instances_file}): "
            ) or local_instances_file
        print(f"Local Instance information file: {local_instances_file}")
    print("\nWriting local vars file...")
    local_vars = round_trip_load(
        str({
            "name": provider_name,
            "type": "local",
            "monkeyfs_path": monkeyfs_path,
            "monkeyfs_scratch": monkeyfs_scratch,
            "local_monkeyfs_path": local_monkeyfs_path,
            "local_instance_details": local_instances_file,
            "monkeyfs_public_ip": monkeyfs_public_ip,
            "monkeyfs_public_port": monkeyfs_public_port,
            "monkeyfs_user": getpass.getuser(),
        }))
    local_vars.fa.set_block_style()
    local_vars.yaml_set_start_comment(
        "\nLocal Provider: {}".format(provider_name))
    local_vars.yaml_add_eol_comment("Defaults to ~/monkeyfs", "monkeyfs_path")
    local_vars.yaml_add_eol_comment("Defaults to ~/monkey-scratch",
                                    "monkeyfs_scratch")
    local_vars.yaml_add_eol_comment(f"Defaults to local.yml",
                                    "local_instance_details")
    write_vars_to_provider(yaml_input, local_vars)
    write_vars_file(local_vars)
    create_local_monkeyfs()

    instance_details_yaml = YAML()
    existing_hosts = OrderedDict()
    try:
        with open(local_instances_file) as f:
            instance_details_yaml = YAML().load(f)
            existing_hosts = instance_details_yaml.get("hosts", OrderedDict())
    except Exception as e:
        print(f"No Local Instances File found: {local_instances_file}...\n" +
              f"Creating {local_instances_file} ")
        instance_details_yaml = CommentedMap()

    print(f"{len(existing_hosts)} existing hosts found")

    local_provider = MonkeyProviderLocal(local_vars)
    for host in existing_hosts:
        print(f"Checking integrity for host: {host}")
        instance = local_provider.create_local_instance(name=host,
                                                        hostname=host)
        if instance is None:
            print(f"FAILED: to create instance {host}")

    if not args.noinput:
        check_inventory_file_for_more_hosts(
            local_provider=local_provider,
            local_vars=local_vars,
            existing_hosts=existing_hosts,
            instance_details_yaml=instance_details_yaml)
    else:

        if args.local_hosts:
            print("Adding specified local hosts...")
            for host_items in args.local_hosts:
                if not host_items:
                    print("Please provide the local_host name to add")
                    continue
                new_host = host_items[0]
                add_and_test_host(local_provider=local_provider,
                                  local_vars=local_vars,
                                  instance_details_yaml=instance_details_yaml,
                                  existing_hosts=existing_hosts,
                                  new_host=new_host)

        write_instance_details(local_vars["local_instance_details"],
                               instance_details_yaml, existing_hosts)


def load_local_inventory_file():
    local_inventory_file = "ansible/inventory/local/inventory.local.yml"
    print(f"Checking Local Inventory File:\n{local_inventory_file}")
    try:
        with open(local_inventory_file) as f:
            inv_yaml = YAML(typ='safe', pure=True)
            inventory_yaml = inv_yaml.load(f)
    except Exception as e:
        print(e)
        print("No Local Inventory File Found")
        inventory_yaml = round_trip_load("---")
    return inventory_yaml


def add_and_test_host(local_provider,
                      local_vars,
                      instance_details_yaml,
                      existing_hosts,
                      new_host,
                      host_group="unknown"):
    print(f"Adding New Host {new_host}...\n")
    new_host_dict = generate_new_host_dict(
        new_host,
        main_group=host_group,
        monkeyfs_public_ip=local_vars["monkeyfs_public_ip"],
        monkeyfs_public_port=local_vars["monkeyfs_public_port"])
    existing_hosts[new_host] = new_host_dict
    write_instance_details(local_vars["local_instance_details"],
                           instance_details_yaml, existing_hosts)
    print(f"Creating instance {new_host}...\n")
    retry = True
    while retry:
        try:

            instance = local_provider.create_local_instance(name=new_host,
                                                            hostname=new_host)
            print(instance)
            if instance is None:
                print(f"failed to create instance {new_host}")
                retry = failed_instance_creation_change_defaults_retry(
                    existing_hosts, new_host)
            else:
                existing_hosts[new_host]["status"] = "unknown"
                break
        except KeyboardInterrupt as e:
            print(
                f"\n\nKeyboard interrupt detected...\nSkipping {new_host}\n" +
                f"Failed to add {new_host}: \n{e}")
            del existing_hosts[new_host]
            continue
        except Exception as e:
            print(f"Failed to add {new_host}: \n{e}")
            retry = failed_instance_creation_change_defaults_retry(
                existing_hosts, new_host)
            continue
    write_instance_details(local_vars["local_instance_details"],
                           instance_details_yaml, existing_hosts)


def failed_instance_creation_change_defaults_retry(existing_hosts, key):
    try:
        default_ip = existing_hosts[key]["monkeyfs_public_ip"]
        default_port = existing_hosts[key]["monkeyfs_public_port"]
        alt_public_ip = input(
            "\nTry an alternative public ip address?" +
            f"\n(ctrl-c to skip host) (default: {default_ip}): ") or default_ip
        print(f"Setting public ip for {key} to {alt_public_ip}")
        alt_public_port = input(
            f"\nTry an alternative public port? ({default_port}) : "
        ) or default_port
        print(f"Setting the port for {key} to {alt_public_port}")

        existing_hosts[key]["monkeyfs_public_ip"] = alt_public_ip
        existing_hosts[key]["monkeyfs_public_port"] = alt_public_port
        return True
    except KeyboardInterrupt as e:
        print(f"\n\nKeyboard interrupt detected...\nSkipping {key}")
        print(f"Failed to add {key}: \n{e}")
        if key in existing_hosts:
            del existing_hosts[key]
        return False


def check_inventory_file_for_more_hosts(local_provider, local_vars,
                                        existing_hosts, instance_details_yaml):
    # Check inventory file for non existing hosts
    inventory_yaml = load_local_inventory_file()

    inv_hosts = walk_inventory("all",
                               local_vars=local_vars,
                               inventory_yaml=inventory_yaml)
    for new_host, host_group in inv_hosts:
        done = 0
        while (new_host not in existing_hosts
               or existing_hosts[new_host]["status"] == "init"):
            inpt = None
            while inpt is None:
                inpt = input(
                    f"'{new_host}', not found in local provider.  \n" +
                    "Add it? (Y/n/s) (Yes/no/skip all): ")
                if inpt == "":
                    inpt = "y"
                inpt = inpt[0].lower()
                if inpt not in ["y", "n", "s"]:
                    inpt = None
            if inpt == "y":
                add_and_test_host(local_provider=local_provider,
                                  local_vars=local_vars,
                                  instance_details_yaml=instance_details_yaml,
                                  existing_hosts=existing_hosts,
                                  new_host=new_host,
                                  host_group=host_group)
            elif inpt == "n":
                print(f"Not adding {new_host}...\n")
            elif inpt == "s":
                print("Skipping all further prompts")
                done = 2
                break
        if done == 2:
            break

    write_instance_details(local_vars["local_instance_details"],
                           instance_details_yaml, existing_hosts)


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


def write_commented_file(filename, yaml_items):
    yaml_items.fa.set_block_style()
    with open(filename, "w") as file:
        try:
            y = YAML()
            y.explicit_start = True
            y.default_flow_style = False
            y.dump(yaml_items, file)
        except Exception as e:
            print(f"Failed to write aws file: {filename}")
            print(e)
            sys.exit(1)


def write_inventory_file(local_inventory):
    ansible_local_file = "ansible/inventory/aws/inventory.compute.aws_ec2.yml"
    write_commented_file(ansible_local_file, local_inventory)


def write_vars_file(local_vars):
    local_vars_file = "ansible/local_vars.yml"
    write_commented_file(local_vars_file, local_vars)

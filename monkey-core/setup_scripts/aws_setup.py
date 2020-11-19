import os
import random
import readline
import string

import ansible_runner
from ruamel.yaml import YAML, round_trip_load

from setup_scripts.utils import (Completer, aws_cred_file_environment,
                                 check_for_existing_local_command,
                                 printout_ansible_events)

comp = Completer()
# we want to treat '/' as part of a word, so override the delimiters
readline.set_completer_delims(' \t\n;')
readline.parse_and_bind("tab: complete")
readline.set_completer(comp.complete)


def check_aws_provider(yaml):
    provider_name = yaml.get("name")
    print("Checking integrity of", provider_name, "with type:",
          yaml.get("type"))

    cred_environment = aws_cred_file_environment(yaml["aws_cred_file"])

    runner = ansible_runner.run(playbook='aws_setup_checks.yml',
                                private_data_dir='ansible',
                                extravars={
                                    "access_key_id":
                                    cred_environment["AWS_ACCESS_KEY_ID"],
                                    "access_key_secret":
                                    cred_environment["AWS_SECRET_ACCESS_KEY"],
                                },
                                quiet=True)
    events = [e for e in runner.events]
    if runner.status == "failed":
        printout_ansible_events(events)

        print("Failed to mount the AWS S3 filesystem")
        return False
    print("Mount successful")

    return True


def create_aws_provider(provider_name, yaml, args):
    details = round_trip_load(str({
        "name": provider_name,
        "type": "aws",
    }))
    details.fa.set_block_style()
    details.yaml_set_start_comment("\nAWS Provider: {}".format(provider_name))

    if check_for_existing_local_command("s3fs") == False:
        print(
            "You must have s3fs installed.\nTo install please follow the instructions here:\n{}"
            .format("https://github.com/s3fs-fuse/s3fs-fuse"))
        exit(1)

    aws_key_file = args.identification_file
    passed_key = False
    if aws_key_file is not None:
        passed_key = True
        aws_key_file = os.path.abspath(aws_key_file)
        try:
            cred_environment = aws_cred_file_environment(aws_key_file)
            valid = True
        except:
            print("Failed to read file")
    if aws_key_file is None or cred_environment is None:
        if args.noinput == True:
            raise ValueError(
                "Please input the identity-file (aws credential key file)")
        valid = False
        while valid == False:
            aws_key_file = input(
                "AWS Account File (should have Access key ID and Secret Access Key in csv form)\nKey: "
            ).strip()
            aws_key_file = os.path.abspath(aws_key_file)
            try:
                cred_environment = aws_cred_file_environment(aws_key_file)
                valid = True
            except:
                print("Failed to read file")

    region_input = args.region or "us-east-1"
    zone_input = args.zone or region_input + "a"
    monkeyfs_input = args.storage_name or "monkeyfs-" + \
        ''.join(random.choice(string.ascii_lowercase) for _ in range(6))
    key_name = args.ssh_key_name
    if not args.noinput:
        region_input = input("Set project region (us-east-1): ") or "us-east-1"
        zone_input = input(
            "Set project zone ({}): ".format(region_input +
                                             "a")) or region_input + "a"
        key_name = input(
            f"Set the access key name ({key_name if not None else 'monkey-aws'}): "
        ) or "monkey-aws"
        print("Zone: ", zone_input)
        if monkeyfs_input is None:
            monkeyfs_input = input("Set the monkey_fs aws s3 bucket name ({})".format("monkeyfs-XXXXXX")) \
                or "monkeyfs-" + ''.join(random.choice(string.ascii_lowercase) for _ in range(6))

    monkeyfs_path = os.path.join(os.getcwd(), "ansible/monkeyfs-aws")

    # Create filesystem bucket and pick a new id if failed
    filesystem_ok = False
    while filesystem_ok == False:

        details["aws_region"] = region_input
        details["aws_zone"] = zone_input
        details["aws_cred_file"] = aws_key_file
        details.yaml_add_eol_comment("Used for mounting filesystems",
                                     "aws_cred_file")

        # "  # Defaults to monkeyfs-XXXXXX to create an unique bucket"
        details["storage_name"] = monkeyfs_input
        details.yaml_set_comment_before_after_key(
            "storage_name", before="\n\n###########\n# Optional\n###########")
        details.yaml_add_eol_comment("Defaults to monkeyfs-XXXXXX",
                                     "storage_name")
        details["local_monkeyfs_path"] = monkeyfs_path
        details["monkeyfs_path"] = "/monkeyfs"  # "  # Defaults to /monkeyfs"
        details.yaml_add_eol_comment("Defaults to /monkeyfs", "monkeyfs_path")

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

        print("\nWriting aws vars file...")
        aws_vars = round_trip_load(
            str({
                "aws_region": region_input,
                "aws_key_name": key_name,  # Sets default key name
                "aws_zone": zone_input,
                "firewall_rule": "monkey-ansible-firewall",
                "storage_name": details["storage_name"],
                "monkeyfs_path": details["monkeyfs_path"],
                "local_monkeyfs_path": monkeyfs_path
            }))
        write_vars_file(aws_vars)

        # Create filesystem and check if succeeded
        filesystem_ok = create_aws_monkeyfs(details["storage_name"],
                                            cred_environment=cred_environment)

        if filesystem_ok == False:
            monkeyfs_input = "monkeyfs-" + \
                ''.join(random.choice(string.ascii_lowercase)
                        for _ in range(6))

    # Creation of FS OK, now mounting FS to local mount point
    if mount_aws_monkeyfs(details) == False:
        print(
            "Terminating, please ensure you have s3fs installed on the core machine"
        )
        exit(1)

    print("\nWriting ansible inventory file...")
    aws_inventory = round_trip_load(
        str({
            "aws_access_key": cred_environment["AWS_ACCESS_KEY_ID"],
            "aws_secret_key": cred_environment["AWS_SECRET_ACCESS_KEY"],
            "plugin": "aws_ec2",
            "regions": [region_input],
            "groups": {
                "monkey": "'monkey' in tags.Name",
                "monkey_aws": "'monkey' in tags.Name",
            },
            "hostnames": ["tag:Name"],
            "filters": {
                "tag:Monkey": "Monkey_AWS"
            },
            "compose": {
                "ansible_host": "public_ip_address",
            }
        }))
    aws_inventory.fa.set_block_style()
    write_inventory_file(aws_inventory)


def write_commented_file(file, yaml):
    yaml.fa.set_block_style()
    with open(file, "w") as file:
        try:
            y = YAML()
            y.explicit_start = True
            y.default_flow_style = False
            y.dump(yaml, file)
        except:
            print("Failed to write aws file: ", file)
            exit(1)


def write_inventory_file(aws_inventory):
    ansible_aws_file = "ansible/inventory/aws/inventory.compute.aws_ec2.yml"
    write_commented_file(ansible_aws_file, aws_inventory)


def write_vars_file(aws_vars):
    aws_vars_file = "ansible/aws_vars.yml"
    write_commented_file(aws_vars_file, aws_vars)


def create_aws_monkeyfs(storage_name, cred_environment):
    print("\nSetting up monkeyfs...")

    runner = ansible_runner.run(playbook='aws_create_fs.yml',
                                private_data_dir='ansible',
                                extravars={
                                    "access_key_id":
                                    cred_environment["AWS_ACCESS_KEY_ID"],
                                    "access_key_secret":
                                    cred_environment["AWS_SECRET_ACCESS_KEY"],
                                },
                                quiet=False)
    events = [e for e in runner.events]

    if runner.status == "failed":
        print("Failed installing and setting up monkeyfs")
        return False
    print("Successfully created AWS S3 bucket: {}".format(storage_name))
    return True


def mount_aws_monkeyfs(yaml):
    bucket_name = yaml["storage_name"]
    local_mount_point = yaml["local_monkeyfs_path"]
    print("Attempting to mount gcs bucket: {} to {}".format(
        bucket_name, local_mount_point))

    cred_environment = aws_cred_file_environment(yaml["aws_cred_file"])

    runner = ansible_runner.run(playbook='aws_setup_checks.yml',
                                private_data_dir='ansible',
                                extravars={
                                    "access_key_id":
                                    cred_environment["AWS_ACCESS_KEY_ID"],
                                    "access_key_secret":
                                    cred_environment["AWS_SECRET_ACCESS_KEY"],
                                },
                                quiet=False)
    events = [e for e in runner.events]
    if runner.status == "failed":
        print("Failed to mount the AWS S3 filesystem")
        return False

    print("Mount successful")
    return True

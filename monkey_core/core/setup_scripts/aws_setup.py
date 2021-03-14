import os
import random
import readline
import string
import sys

import ansible_runner
from core.setup_scripts.utils import (Completer, aws_cred_file_environment,
                                      check_for_existing_local_command,
                                      printout_ansible_events)
from ruamel.yaml import YAML, round_trip_load

comp = Completer()
# we want to treat '/' as part of a word, so override the delimiters
readline.set_completer_delims(' \t\n;')
readline.parse_and_bind("tab: complete")
readline.set_completer(comp.complete)


def check_aws_provider(yaml):
    provider_name = yaml.get("name")
    print("Checking integrity of", provider_name, "with type:", yaml.get("type"))

    cred_environment = aws_cred_file_environment(yaml["aws_cred_file"])

    runner = ansible_runner.run(
        playbook='aws_setup_checks.yml',
        private_data_dir='ansible',
        extravars={
            "access_key_id": cred_environment["AWS_ACCESS_KEY_ID"],
            "access_key_secret": cred_environment["AWS_SECRET_ACCESS_KEY"],
        },
        quiet=True)

    if runner.status == "failed":
        events = [e for e in runner.events]
        printout_ansible_events(events)
        print("Failed to mount the AWS S3 filesystem")
        return False
    print("Mount successful")

    return True


def generate_random_monkeyfs_name():
    return "monkeyfs-" + ''.join(random.choice(string.ascii_lowercase) for _ in range(6))


def create_aws_provider(provider_name, provider_yaml, args):
    provider_type = "aws"
    aws_key_file = args.identification_file
    ssh_key_name = args.ssh_key_name
    region_input = args.region
    zone_input = args.zone
    local_monkeyfs_path = os.path.join(os.getcwd(), "ansible/monkeyfs-aws")
    monkeyfs_path = "/monkeyfs"
    aws_storage_name = args.storage_name or generate_random_monkeyfs_name()

    if not check_for_existing_local_command("s3fs"):
        print("You must have s3fs installed.\n " +
              "To install please follow the instructions here:\n" +
              ("https://github.com/s3fs-fuse/s3fs-fuse"))
        exit(1)

    cred_environment = None
    if aws_key_file is not None:
        aws_key_file = os.path.abspath(aws_key_file)
        try:
            cred_environment = aws_cred_file_environment(aws_key_file)
            valid = True
        except:
            print("Failed to read file")
    if aws_key_file is None or cred_environment is None:
        if args.noinput:
            raise ValueError("Please input the identity-file (aws credential key file)")
        while True:
            aws_key_file = input(
                "AWS Account File (should have Access key ID and Secret Access Key in csv form)\n"
                + "Key: ").strip()
            aws_key_file = os.path.abspath(aws_key_file)
            try:
                cred_environment = aws_cred_file_environment(aws_key_file)
                break
            except:
                print("Failed to read and parse credentials")

    def get_input_with_defaults(prompt_phrase, prompt_name, default_value, noinput):
        if noinput:
            print(f"{prompt_name} not provider. Defaulting to: {default_value}")
            return default_value
        return input(f"{prompt_phrase} ({default_value}): ") or default_value

    if not args.region:
        region_input = get_input_with_defaults(prompt_phrase="Set AWS region",
                                               prompt_name="AWS Region",
                                               default_value="us-east-1",
                                               noinput=args.noinput)

    if not args.zone:
        zone_input = get_input_with_defaults(prompt_phrase="Set AWS Zone",
                                             prompt_name="AWS Zone",
                                             default_value=region_input + "a",
                                             noinput=args.noinput)

    if not args.ssh_key_name:
        ssh_key_name = get_input_with_defaults(prompt_phrase="Set AWS SSH Key Name",
                                               prompt_name="AWS ssh key name",
                                               default_value="monkey_aws",
                                               noinput=args.noinput)

    if not args.storage_name:
        filesystem_ok = False
        while not filesystem_ok:
            if not args.noinput and not args.storage_name:
                aws_storage_name = input("Set the monkey_fs aws s3 bucket name ({})"
                                         .format(aws_storage_name)) or aws_storage_name
            filesystem_ok = create_aws_monkeyfs(storage_name=aws_storage_name,
                                                cred_environment=cred_environment,
                                                region=region_input)

            if not filesystem_ok:
                if not args.storage_name:
                    print(f"Failed creating bucket: {aws_storage_name}\n" +
                          "Ensure storage_name is unique and AWS allowed")
                    sys.exit(1)
                aws_storage_name = generate_random_monkeyfs_name()

    print(f"Aws Credenitals File: {aws_key_file}")
    print(f"Aws Region: {region_input}")
    print(f"Aws Zone: {zone_input}")
    print(f"Aws Key Name: {ssh_key_name}")
    print(f"Aws Bucket Name: {aws_storage_name}")

    aws_vars = round_trip_load(
        str({
            "name": provider_name,
            "type": provider_type,
            "aws_region": region_input,
            "aws_zone": zone_input,
            "aws_cred_file": aws_key_file,
            "aws_key_name": ssh_key_name,
            "storage_name": aws_storage_name,
            "local_monkeyfs_path": local_monkeyfs_path,
            "monkeyfs_path": monkeyfs_path,
            "firewall_rule": "monkey-ansible-firewall",
        }))
    aws_vars.fa.set_block_style()
    aws_vars.yaml_set_start_comment("\nAWS Provider: {}".format(provider_name))
    aws_vars.yaml_add_eol_comment("Used for mounting filesystems", "aws_cred_file")
    aws_vars.yaml_set_comment_before_after_key(
        "storage_name", before="\n\n###########\n# Optional\n###########")
    aws_vars.yaml_add_eol_comment("Defaults to monkeyfs-XXXXXX", "storage_name")
    aws_vars.yaml_add_eol_comment("Defaults to /monkeyfs", "monkeyfs_path")

    # Create filesystem bucket and pick a new id if failed
    providers = provider_yaml.get("providers", [])
    if providers is None:
        providers = []
    providers.append(aws_vars)
    provider_yaml["providers"] = providers

    print("\nWriting to providers.yml...")
    with open('providers.yml', 'w') as file:
        y = YAML()
        provider_yaml.fa.set_block_style()
        y.explicit_start = True
        y.default_flow_style = False
        y.dump(provider_yaml, file)

    print("\nWriting aws vars file...")
    write_vars_file(aws_vars)

    # Creation of FS OK, now mounting FS to local mount point
    if not mount_aws_monkeyfs(aws_vars):
        print("Terminating, please ensure you have s3fs installed on the core machine")
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


def write_commented_file(filename, yaml_params):
    yaml_params.fa.set_block_style()
    with open(filename, "w") as f:
        try:
            y = YAML()
            y.explicit_start = True
            y.default_flow_style = False
            y.dump(yaml_params, f)
        except Exception as e:
            print(f"Failed to write aws file: {filename}\n{e}")
            exit(1)


def write_inventory_file(aws_inventory):
    ansible_aws_file = "ansible/inventory/aws/inventory.compute.aws_ec2.yml"
    write_commented_file(ansible_aws_file, aws_inventory)


def write_vars_file(aws_vars):
    aws_vars_file = "ansible/aws_vars.yml"
    write_commented_file(aws_vars_file, aws_vars)


def create_aws_monkeyfs(storage_name, cred_environment, region):
    print("\nSetting up monkeyfs...")
    runner = ansible_runner.run(
        playbook='aws_create_fs.yml',
        private_data_dir='ansible',
        extravars={
            "access_key_id": cred_environment["AWS_ACCESS_KEY_ID"],
            "access_key_secret": cred_environment["AWS_SECRET_ACCESS_KEY"],
            "storage_name": storage_name,
            "aws_region": region
        },
        quiet=False)

    if runner.status == "failed":
        print("Failed installing and setting up monkeyfs")
        return False
    print("Successfully created AWS S3 bucket: {}".format(storage_name))
    return True


def mount_aws_monkeyfs(yaml):
    bucket_name = yaml["storage_name"]
    local_mount_point = yaml["local_monkeyfs_path"]
    print("Attempting to mount s3 bucket: {} to {}".format(bucket_name,
                                                           local_mount_point))

    cred_environment = aws_cred_file_environment(yaml["aws_cred_file"])

    runner = ansible_runner.run(
        playbook='aws_setup_checks.yml',
        private_data_dir='ansible',
        extravars={
            "access_key_id": cred_environment["AWS_ACCESS_KEY_ID"],
            "access_key_secret": cred_environment["AWS_SECRET_ACCESS_KEY"],
        },
        quiet=False)
    if runner.status == "failed":
        print("Failed to mount the AWS S3 filesystem")
        return False

    print("Mount successful")
    return True

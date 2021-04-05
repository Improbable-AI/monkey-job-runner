import os
import readline
import sys

import ansible_runner
from core.setup_scripts.utils import (Completer, aws_cred_file_environment,
                                      check_for_existing_local_command,
                                      generate_random_monkeyfs_name,
                                      get_input_with_defaults,
                                      printout_ansible_events,
                                      write_commented_yaml_file,
                                      write_vars_file)
from ruamel.yaml import round_trip_load


def failed_setup_provider_remove_files():
    aws_vars_file = "ansible/aws_vars.yml"
    try:
        os.remove(aws_vars_file)
    except Exception:
        pass
    ansible_inventory_file = "ansible/inventory/aws/inventory.compute.aws_ec2.yml"
    try:
        os.remove(ansible_inventory_file)
    except Exception:
        pass
    providers_file = "providers.yml"


def check_aws_provider(yaml):
    provider_name = yaml.get("name")
    print("Checking integrity of", provider_name, "with type:",
          yaml.get("type"))

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


def check_system_dependencies():
    if not check_for_existing_local_command("s3fs"):
        print("You must have s3fs installed.\n " +
              "To install please follow the instructions here:\n" +
              ("https://github.com/s3fs-fuse/s3fs-fuse"))
        exit(1)


def get_key_file(args):
    key_file = args.identification_file
    if key_file is not None:
        key_file = os.path.abspath(key_file)
        try:
            return key_file, aws_cred_file_environment(key_file)
        except Exception:
            print(f"Failed to read file provided key file {key_file}")
            sys.exit(1)
    if args.noinput:
        raise ValueError(
            "Please input the identity-file (aws credential key file)")
    while True:
        key_file = input(
            "AWS Account File (should have Access key ID and Secret Access Key in csv form)\n"
            + "Key: ").strip()
        key_file = os.path.abspath(key_file)
        try:
            return key_file, aws_cred_file_environment(key_file)
        except Exception:
            print("Failed to read and parse credentials")


def get_valid_storage_name_input(args, storage_name, region, cred_environment):
    filesystem_ok = False
    while not filesystem_ok:
        if not args.noinput and not args.storage_name:
            storage_name = input("Set the monkey_fs aws s3 bucket name ({})"
                                 .format(storage_name)) or storage_name
        filesystem_ok = create_aws_monkeyfs(storage_name=storage_name,
                                            cred_environment=cred_environment,
                                            region=region)

        if not filesystem_ok:
            if not args.storage_name:
                print(f"Failed creating bucket: {storage_name}\n" +
                      "Ensure storage_name is unique and AWS allowed")
                sys.exit(1)
            storage_name = generate_random_monkeyfs_name()
    return storage_name


def create_aws_provider(provider_name, provider_yaml, args):
    provider_type = "aws"
    ssh_key_name = args.ssh_key_name
    region_input = args.region
    zone_input = args.zone
    local_monkeyfs_path = os.path.join(os.getcwd(), "ansible/monkeyfs-aws")
    monkeyfs_path = "/monkeyfs"
    aws_storage_name = args.storage_name or generate_random_monkeyfs_name()

    aws_key_file, cred_environment = get_key_file(args=args,)

    if not args.region:
        region_input = get_input_with_defaults(
            prompt_phrase="Set AWS region",
            prompt_name="AWS Region",
            default_value="us-east-1",
            noinput=args.noinput,
        )

    if not args.zone:
        zone_input = get_input_with_defaults(
            prompt_phrase="Set AWS Zone",
            prompt_name="AWS Zone",
            default_value=region_input + "a",
            noinput=args.noinput,
        )

    if not args.ssh_key_name:
        ssh_key_name = get_input_with_defaults(
            prompt_phrase="Set AWS SSH Key Name",
            prompt_name="AWS ssh key name",
            default_value="monkey_aws",
            noinput=args.noinput,
        )

    if not args.storage_name:
        aws_storage_name = get_valid_storage_name_input(
            args=args,
            storage_name=aws_storage_name,
            region=region_input,
            cred_environment=cred_environment)

    print(f"Aws Credenitals File: {aws_key_file}")
    print(f"Aws Region: {region_input}")
    print(f"Aws Zone: {zone_input}")
    print(f"Aws Key Name: {ssh_key_name}")
    print(f"Aws Bucket Name: {aws_storage_name}")

    raw_aws_vars = {
        "name": provider_name,
        "type": provider_type,
        "aws_region": region_input,
        "aws_zone": zone_input,
        "aws_cred_file": aws_key_file,
        "aws_key_name": ssh_key_name,
        "aws_storage_name": aws_storage_name,
        "local_monkeyfs_path": local_monkeyfs_path,
        "monkeyfs_path": monkeyfs_path,
        "firewall_rule": "monkey-ansible-firewall",
    }

    write_vars_file(raw_vars=raw_aws_vars,
                    provider_name=provider_name,
                    provider_yaml=provider_yaml,
                    file_name="aws_vars.yml",
                    before_comments={
                        # "aws_storage_name":
                        #     "\n\n###########\n# Optional\n###########",
                    },
                    end_line_comments={
                        "aws_storage_name": "Defautls to monkeyfs-XXXXXX",
                        "monkeyfs_path": "Defautls to /monkeyfs"
                    })

    if not mount_aws_monkeyfs(raw_aws_vars):
        print(
            "Terminating, failed to mount the aws filesystem"
        )
        exit(1)

    print("\nWriting ansible inventory file...")
    write_inventory_file(
        cred_environment=cred_environment,
        region=region_input,
    )
    return True


def write_inventory_file(cred_environment, region):
    aws_inventory = round_trip_load(
        str({
            "aws_access_key": cred_environment["AWS_ACCESS_KEY_ID"],
            "aws_secret_key": cred_environment["AWS_SECRET_ACCESS_KEY"],
            "plugin": "aws_ec2",
            "regions": [region],
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
    ansible_inventory_file = "ansible/inventory/aws/inventory.compute.aws_ec2.yml"
    os.makedirs("ansible/inventory/aws/", exist_ok=True)
    write_commented_yaml_file(ansible_inventory_file, aws_inventory)


def create_aws_monkeyfs(storage_name, cred_environment, region):
    print("\nSetting up monkeyfs...")
    runner = ansible_runner.run(
        playbook='aws_create_fs.yml',
        private_data_dir='ansible',
        extravars={
            "access_key_id": cred_environment["AWS_ACCESS_KEY_ID"],
            "access_key_secret": cred_environment["AWS_SECRET_ACCESS_KEY"],
            "aws_storage_name": storage_name,
            "aws_region": region
        },
        quiet=False)

    if runner.status == "failed":
        print("Failed installing and setting up monkeyfs")
        return False
    print("Successfully created AWS S3 bucket: {}".format(storage_name))
    return True


def mount_aws_monkeyfs(yaml):
    bucket_name = yaml["aws_storage_name"]
    local_mount_point = yaml["local_monkeyfs_path"]
    print("Attempting to mount s3 bucket: {} to {}".format(
        bucket_name, local_mount_point))

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

import os
from ruamel.yaml import YAML, round_trip_load
import ansible_runner
import random
import string


def check_aws_provider(yaml):
    provider_name = yaml.get("name")
    print("Checking integrity of", provider_name,
          "with type:", yaml.get("type"))
    storage_name = yaml.get("storage_name")

    print("Checking if {} is mounted".format(storage_name))
    runner = ansible_runner.run(playbook='aws_setup_checks.yml',
                                private_data_dir='ansible',
                                quiet=False)
    events = [e for e in runner.events]
    if len(runner.stats.get("failures")) != 0:
        print("Failed to mount the AWS S3 filesystem")
        return False
    print("Mount successful")

    return True


def create_aws_provider(provider_name, yaml, args):
    details = round_trip_load(str({
        "name": provider_name,
        "type": "aws",
    }))

    region_input = args.region or "us-east-1"
    zone_input = args.zone or region_input + "-b"
    monkeyfs_input = args.storage_name or "monkeyfs-" + \
        ''.join(random.choice(string.ascii_lowercase) for _ in range(6))
    if args.noinput == False:
        region_input = input("Set project region (us-east-1): ") or "us-east-1"
        zone_input = input("Set project region ({}): ".format(
            region_input + "-b")) or region_input + "-b"
        if monkeyfs_input is None:
            monkeyfs_input = input("Set the monkey_fs aws s3 bucket name ({})".format("monkeyfs-XXXXXX")) \
                or "monkeyfs-" + ''.join(random.choice(string.ascii_lowercase) for _ in range(6))
    monkeyfs_path = os.path.join(os.getcwd(), "ansible/monkeyfs-aws")

    filesystem_ok = False
    # Create filesystem bucket and pick a new id if failed
    while filesystem_ok == False:
        details["aws_region"] = region_input
        details["aws_zone"] = zone_input

        # "  # Defaults to keys/monkey-aws"
        details["aws_ssh_private_key_path"] = None
        details.yaml_set_comment_before_after_key(
            "aws_ssh_private_key_path", before="\n\n###########\n# Optional\n###########")
        details.yaml_add_eol_comment(
            "Defaults to keys/aws", "aws_ssh_private_key_path")
        # "  # Defaults to monkeyfs-XXXXXX to create an unique bucket"
        details["storage_name"] = monkeyfs_input
        details.yaml_add_eol_comment(
            "Defaults to monkeyfs-XXXXXX", "storage_name")
        details["local_monkeyfs_path"] = monkeyfs_path
        details["monkeyfs_path"] = None  # "  # Defaults to /monkeyfs"
        details.yaml_add_eol_comment("Defaults to /monkeyfs", "monkeyfs_path")

        providers = yaml.get("providers", [])
        if providers is None:
            providers = []
        providers.append(details)
        yaml["providers"] = providers

        print("\nWriting to providers.yml...")
        with open('providers.yml', 'w') as file:
            y = YAML()
            y.explicit_start = True
            y.default_flow_style = False
            y.dump(yaml, file)

        print("\nWriting aws vars file...")
        aws_vars = round_trip_load(str({
            "aws_region": region_input,
            "aws_key_name": "monkey-aws",  # Sets default key name
            "aws_zone": zone_input,
            "firewall_rule": "monkey-ansible-firewall",
            "aws_ssh_private_key_path": details["aws_ssh_private_key_path"],
            "storage_name": details["storage_name"],
            "monkeyfs_path": details["monkeyfs_path"],
            "local_monkeyfs_path": monkeyfs_path
        }))
        write_vars_file(aws_vars)

        # Create filesystem and check if succeeded
        filesystem_ok = create_aws_monkeyfs(details["storage_name"])

        if filesystem_ok == False:
            monkeyfs_input = "monkeyfs-" + \
                ''.join(random.choice(string.ascii_lowercase)
                        for _ in range(6))

    # Creation of FS OK, now mounting FS to local mount point
    if mount_aws_monkeyfs(details) == False:
        print("Terminating, please ensure you have gcsfuse installed on the core machine")
        exit(1)

    print("\nWriting ansible inventory file...")
    aws_inventory = round_trip_load(str({
        "plugin": "aws_ec2",
        "regions": [region_input],
        "groups": {
            "monkey": "'monkey' in tags.Name",
            "monkey_aws": "'monkey' in tags.Name",
        },
        "hostnames": ["tag:Name"],
        "filters": {
            "tag:Monkey": "Yes"
        },
        "compose": {
            "ansible_host": "public_ip_address"
        }
    }))
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
            print("Failed to write aws  file")
            exit(1)


def write_inventory_file(aws_inventory):
    ansible_aws_file = "ansible/inventory/aws/inventory.compute.aws_ec2.yml"
    write_commented_file(ansible_aws_file, aws_inventory)


def write_vars_file(aws_vars):
    aws_vars_file = "ansible/aws_vars.yml"
    write_commented_file(aws_vars_file, aws_vars)


def create_aws_monkeyfs(storage_name):
    print("\nSetting up monkeyfs...")

    runner = ansible_runner.run(playbook='aws_create_fs.yml',
                                private_data_dir='ansible',
                                quiet=False)
    events = [e for e in runner.events]

    if len(runner.stats.get("failures")) != 0:
        print("Failed installing and setting up monkeyfs")
        return False
    print("Successfully created AWS S3 bucket: {}".format(storage_name))
    return True


def mount_aws_monkeyfs(yaml):
    bucket_name = yaml["storage_name"]
    local_mount_point = yaml["local_monkeyfs_path"]
    print("Attempting to mount gcs bucket: {} to {}".format(
        bucket_name, local_mount_point))
    runner = ansible_runner.run(playbook='aws_setup_checks.yml',
                                private_data_dir='ansible',
                                quiet=False)
    events = [e for e in runner.events]
    if len(runner.stats.get("failures")) != 0:
        print("Failed to mount the AWS S3 filesystem")
        return False

    print("Mount successful")
    return True

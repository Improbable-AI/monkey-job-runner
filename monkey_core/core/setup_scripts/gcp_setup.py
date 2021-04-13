import os
import readline
import sys

import ansible_runner
from core.setup_scripts.utils import (Completer,
                                      check_for_existing_local_command,
                                      gcp_cred_file_environment,
                                      generate_random_monkeyfs_name,
                                      get_input_with_defaults,
                                      write_commented_yaml_file,
                                      write_vars_file)
from ruamel.yaml import round_trip_load


def check_gcp_provider(yaml):
    provider_name = yaml.get("name")
    print("Checking integrity of", provider_name, "with type:",
          yaml.get("type"))

    runner = ansible_runner.run(playbook='gcp_setup_checks.yml',
                                private_data_dir='ansible',
                                quiet=False)
    if runner.status == "failed":
        print("Failed to mount the GCS filesystem")
        return False
    print("Mount successful")

    return True


def check_system_dependencies():
    if not check_for_existing_local_command("gcsfuse"):
        print(
            "You must have gcsfuse installed." +
            "\nTo install please follow the instructions here:" +
            "\nhttps://github.com/GoogleCloudPlatform/gcsfuse/blob/master/docs/installing.md"
        )
        exit(1)
    if not check_for_existing_local_command("gcloud"):
        print("You must have gcloud installed." +
              "\nto install please follow the instructions here:" +
              "\nhttps://cloud.google.com/sdk/docs/install")
        exit(1)


def get_key_file(args):
    key_file = args.identification_file
    if key_file is not None:
        key_file = os.path.abspath(key_file)
        try:
            return key_file, gcp_cred_file_environment(key_file)
        except Exception:
            print(f"Failed to read file provided key file {key_file}")
            sys.exit(1)
    if args.noinput:
        raise ValueError(
            "Please input the identity-file (gcp credential key file)")
    while True:
        key_file = input(
            "GCP Account File (should have service account secrets in json)\n"
            + "Key: ").strip()
        key_file = os.path.abspath(key_file)
        try:
            return key_file, gcp_cred_file_environment(key_file)
        except Exception:
            print("Failed to read and parse credentials")


def get_valid_storage_name_input(args, storage_name, credentials):
    filesystem_ok = False
    while not filesystem_ok:
        if not args.noinput and not args.storage_name:
            storage_name = input(
                f"Set the monkey_fs gcp gcs bucket name ({storage_name}): "
            ) or storage_name
        credentials["gcp_storage_name"] = storage_name
        filesystem_ok = create_gcp_monkeyfs(credentials=credentials)

        if not filesystem_ok:
            if not args.storage_name:
                print(f"Failed creating bucket: {storage_name}\n" +
                      "Ensure storage_name is unique and AWS allowed")
                sys.exit(1)
            storage_name = generate_random_monkeyfs_name()
    return storage_name


def create_gcp_provider(provider_name, provider_yaml, args):
    provider_type = "gcp"
    ssh_key_name = args.ssh_key_name
    region_input = args.region
    zone_input = args.zone
    local_monkeyfs_path = os.path.join(os.getcwd(), "ansible/monkeyfs-gcp")
    monkeyfs_path = "/monkeyfs"
    gcp_storage_name = args.storage_name or generate_random_monkeyfs_name()
    gcp_project = None
    gcp_service_email = None
    gcp_user = None

    while gcp_project is None:
        gcp_key_file, cred_environment = get_key_file(args=args)
        try:
            gcp_user = f"sa_{cred_environment['client_id']}"
            gcp_service_email = cred_environment["client_email"]
            gcp_project = cred_environment["project_id"]
        except Exception as e:
            print(e)
            print(
                "Unable to find {project_id} in gcp service account file: {gcp_key_file}"
            )

    if not args.region:
        region_input = get_input_with_defaults(
            prompt_phrase="Set GCP region",
            prompt_name="GCP Region",
            default_value="us-east1",
            noinput=args.noinput,
        )

    if not args.zone:
        zone_input = get_input_with_defaults(
            prompt_phrase="Set GCP Zone",
            prompt_name="GCP Zone",
            default_value=region_input + "-b",
            noinput=args.noinput,
        )

    if not args.ssh_key_name:
        ssh_key_name = get_input_with_defaults(
            prompt_phrase="Set GCP SSH Key Name",
            prompt_name="GCP ssh key name",
            default_value="monkey_gcp",
            noinput=args.noinput,
        )

    if not args.storage_name:
        gcp_storage_name = get_valid_storage_name_input(
            args=args,
            storage_name=gcp_storage_name,
            credentials={
                "gcp_project": gcp_project,
                "gcp_cred_kind": "serviceaccount",
                "gcp_cred_file": gcp_key_file,
                "gcp_region": region_input
            })

    print(f"Gcp Credenitals File: {gcp_key_file}")
    print(f"Gcp Region: {region_input}")
    print(f"Gcp Zone: {zone_input}")
    print(f"Gcp SSH Key Name: {ssh_key_name}")
    print(f"Gcp Bucket Name: {gcp_storage_name}")

    raw_gcp_vars = {
        "name": provider_name,
        "type": provider_type,
        "gcp_cred_file": gcp_key_file,
        "gcp_cred_kind": "serviceaccount",
        "gcp_project": gcp_project,
        "gcp_user": gcp_user,
        "gcp_service_email": gcp_service_email,
        "gcp_region": region_input,
        "gcp_zone": zone_input,
        "gcp_key_name": ssh_key_name,
        "gcp_storage_name": gcp_storage_name,
        "local_monkeyfs_path": local_monkeyfs_path,
        "monkeyfs_path": monkeyfs_path,
        "firewall_rule": "monkey-ansible-firewall"
    }

    write_vars_file(
        raw_vars=raw_gcp_vars,
        provider_name=provider_name,
        provider_yaml=provider_yaml,
        file_name="gcp_vars.yml",
        before_comments={
            # "gcp_storage_name":
            #     "\n\n###########\n# Optional\n###########",
        },
        end_line_comments={
            "gcp_storage_name": "Defautls to monkeyfs-XXXXXX",
            "monkeyfs_path": "Defautls to /monkeyfs"
        })

    if not mount_gcp_monkeyfs(raw_gcp_vars):
        print("Terminating, failed to mount the gcp filesystem")
        exit(1)

    print("\nWriting ansible inventory file...")
    write_inventory_file(gcp_vars=raw_gcp_vars)
    return True


def write_inventory_file(gcp_vars):
    gcp_inventory = round_trip_load(
        str({
            "plugin": "gcp_compute",
            "projects": [gcp_vars["gcp_project"]],
            "regions": [gcp_vars["gcp_region"]],
            "keyed_groups": [{
                "key": "zone"
            }],
            "groups": {
                "monkey": "'monkey' in name",
                "monkey_gcp": "'monkey' in name",
            },
            "hostnames": ["name"],
            "filters": [],
            "auth_kind": "serviceaccount",
            "service_account_file": gcp_vars["gcp_cred_file"],
            "compose": {
                "ansible_host": "networkInterfaces[0].accessConfigs[0].natIP"
            }
        }))
    ansible_inventory_file = "ansible/inventory/gcp/inventory.compute.gcp.yml"
    os.makedirs("ansible/inventory/gcp/", exist_ok=True)
    write_commented_yaml_file(filename=ansible_inventory_file,
                              yaml_params=gcp_inventory)


def create_gcp_monkeyfs(credentials):
    print("\nSetting up monkeyfs...")

    runner = ansible_runner.run(playbook='gcp_create_fs.yml',
                                private_data_dir='ansible',
                                extravars=credentials,
                                quiet=False)

    if runner.status == "failed":
        print("Failed installing and setting up monkeyfs")
        return False

    storage_name = credentials.get("gcp_storage_name", "monkeyfs-gcp")
    print(f"Successfully created GCS bucket: {storage_name}")
    return True


def mount_gcp_monkeyfs(yaml):
    bucket_name = yaml.get("gcp_storage_name", "monkeyfs-gcp")
    local_mount_point = yaml["local_monkeyfs_path"]
    print(f"Attempting mount gcs: {bucket_name} to {local_mount_point}")
    runner = ansible_runner.run(playbook='gcp_setup_checks.yml',
                                private_data_dir='ansible',
                                quiet=False)
    if runner.status == "failed":
        print("Failed to mount the GCS filesystem")
        return False

    print("Mount successful")
    return True

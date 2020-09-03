import os
from ruamel.yaml import YAML, round_trip_load
import ansible_runner
import random
import string

def check_gcp_provider(yaml):
    provider_name = yaml.get("name")
    print("Checking integrity of", provider_name, "with type:", yaml.get("type"))
    storage_name = yaml.get("storage_name")

    print("Checking if {} is mounted".format(storage_name))
    runner = ansible_runner.run(playbook='gcp_setup_checks.yml', 
                                private_data_dir='ansible',
                                quiet=False)
    events = [e for e in runner.events]
    if len(runner.stats.get("failures")) != 0:
        print("Failed to mount the GCS filesystem")
        return False
    print("Mount successful")

    return True

def create_gcp_provider(provider_name, yaml, args):
    details = round_trip_load(str({
        "name": provider_name,
        "type": "gcp",
        "project": "",
        "gcp_cred_kind": "serviceaccount",
        "gcp_cred_file": "",
    }))
    
    while details["project"] == "":
        service_account_file = args.identification_file
        passed_key = False
        if service_account_file is not None:
            passed_key = True
            service_account_file = os.path.abspath(service_account_file)  
        
        if service_account_file is None and args.noinput == False:
            service_account_file = input("GCP Service Account File: ")
            service_account_file = os.path.abspath(service_account_file)  
        elif service_account_file is None:
            print("Please pass in an service account with -i/--identification-file")
            exit(1)
        try:
            with open(service_account_file) as file:
                print("Loading service account...")
                y = YAML()
                sa_details = y.load(file)
                details.fa.set_block_style()
                details.yaml_set_start_comment("\nGCP Provider: {}".format(provider_name))
                details["project"] = sa_details["project_id"]
                project = sa_details["project_id"]
                details["gcp_cred_file"] = service_account_file
        except Exception as e:
            print(e)
            print("Unable to parse service account file")
            if passed_key:
                exit(1)
            continue
    region_input = args.region or "us-east1"
    zone_input = args.zone or region_input + "-b"
    monkeyfs_input = args.storage_name or "monkeyfs-" + ''.join(random.choice(string.ascii_lowercase) for _ in range(6))
    if args.noinput == False:
        region_input = input("Set project region (us-east1): ") or "us-east1"
        zone_input = input("Set project region ({}): ".format(region_input + "-b")) or region_input + "-b"
        if monkeyfs_input is None:
            monkeyfs_input = input("Set the monkey_fs gcs bucket name ({})".format("monkeyfs-XXXXXX")) \
                or "monkeyfs-" + ''.join(random.choice(string.ascii_lowercase) for _ in range(6))
    monkeyfs_path = os.path.join(os.getcwd(), "ansible/monkeyfs-gcp")

    filesystem_ok = False
    # Create filesystem bucket and pick a new id if failed
    while filesystem_ok == False:
    
        details["gcp_region"] = region_input
        details["gcp_zone"] = zone_input
        
        details["gcp_ssh_private_key_path"] = None #  "  # Defaults to keys/gcp"
        details.yaml_set_comment_before_after_key("gcp_ssh_private_key_path", before="\n\n###########\n# Optional\n###########")
        details.yaml_add_eol_comment("Defaults to keys/gcp", "gcp_ssh_private_key_path")
        details["storage_name"] = monkeyfs_input #  "  # Defaults to monkeyfs-XXXXXX to create an unique bucket"
        details.yaml_add_eol_comment("Defaults to monkeyfs-XXXXXX", "storage_name")
        details["local_monkeyfs_path"] = monkeyfs_path
        details["monkeyfs_path"] = None #  "  # Defaults to /monkeyfs"
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
        
        print("\nWriting gcp vars file...")
        gcp_vars = round_trip_load(str({
            "gcp_cred_kind": "serviceaccount", 
            "gcp_cred_file": service_account_file,
            "gcp_region": region_input,
            "gcp_zone": zone_input,
            "firewall_rule": "monkey-ansible-firewall",
            "gcp_ssh_private_key_path": details["gcp_ssh_private_key_path"],
            "storage_name": details["storage_name"],
            "monkeyfs_path": details["monkeyfs_path"],
            "local_monkeyfs_path": monkeyfs_path
        }))
        write_vars_file(gcp_vars)

        # Create filesystem and check if succeeded
        filesystem_ok = create_gcp_monkeyfs(details["storage_name"])

        if filesystem_ok == False:
            monkeyfs_input = "monkeyfs-" + ''.join(random.choice(string.ascii_lowercase) for _ in range(6))

    # Creation of FS OK, now mounting FS to local mount point
    if mount_gcp_monkeyfs(details) == False:
        print("Terminating, please ensure you have gcsfuse installed on the core machine")
        exit(1)

    print("\nWriting ansible inventory file...")
    gcp_inventory = round_trip_load(str({
        "plugin": "gcp_compute", 
        "projects": [project],
        "regions": [region_input], 
        "keyed_groups": [{"key": "zone"}],
        "groups": {
            "monkey": "'monkey' in name",
            "monkey_gcp": "'monkey' in name",
        },
        "hostnames": ["name"],
        "filters": [],
        "auth_kind": "serviceaccount", 
        "service_account_file": service_account_file,
        "compose": {
            "ansible_host": "networkInterfaces[0].accessConfigs[0].natIP"
        }
    }))
    write_inventory_file(gcp_inventory)

def write_commented_file(file, yaml):
    yaml.fa.set_block_style()
    with open(file, "w") as file:
        try:
            y = YAML()
            y.explicit_start = True
            y.default_flow_style = False
            y.dump(yaml, file)
        except:
            print("Failed to write gcp inventory file")
            exit(1)
def write_inventory_file(gcp_inventory):
    ansible_gcp_file = "ansible/inventory/gcp/inventory.compute.gcp.yml"
    write_commented_file(ansible_gcp_file, gcp_inventory)
    
def write_vars_file(gcp_vars):
    gcp_vars_file = "ansible/gcp_vars.yml"
    write_commented_file(gcp_vars_file, gcp_vars)

def create_gcp_monkeyfs(storage_name):
    print("\nSetting up monkeyfs...")
    
    runner = ansible_runner.run(playbook='gcp_create_fs.yml', 
                                                            private_data_dir='ansible',
                                                            quiet=False)
    events = [e for e in runner.events]

    if len(runner.stats.get("failures")) != 0:
        print("Failed installing and setting up monkeyfs")
        return False
    print("Successfully created GCS bucket: {}".format(storage_name))
    return True

def mount_gcp_monkeyfs(yaml):
    bucket_name = yaml["storage_name"]
    local_mount_point = yaml["local_monkeyfs_path"]
    print("Attempting to mount gcs bucket: {} to {}".format(bucket_name, local_mount_point))
    runner = ansible_runner.run(playbook='gcp_setup_checks.yml', 
                                private_data_dir='ansible',
                                quiet=False)
    events = [e for e in runner.events]
    if len(runner.stats.get("failures")) != 0:
        print("Failed to mount the GCS filesystem")
        return False

    print("Mount successful")
    return True
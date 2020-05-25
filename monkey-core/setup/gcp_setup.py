import os
from ruamel.yaml import YAML, round_trip_load
import ansible_runner

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
  if args.noinput == False:
    region_input = input("Set project region (us-east1): ")
    zone_input = input("Set project region ({}): ".format(region_input + "-b")) or region_input + "-b"
  
  details["region"] = region_input
  details["zone"] = zone_input
  
  details["gcp_ssh_private_key_path"] = None #  "  # Defaults to keys/gcp"
  details.yaml_set_comment_before_after_key("gcp_ssh_private_key_path", before="\n\n###########\n# Optional\n###########")
  details.yaml_add_eol_comment("Defaults to keys/gcp", "gcp_ssh_private_key_path")
  details["gcp_storage_name"] = None #  "  # Defaults to monkeyfs"
  details.yaml_add_eol_comment("Defaults to monkeyfs", "gcp_storage_name")
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

  print("\nWriting ansible inventory file...")
  ansible_gcp_file = "ansible/inventory/gcp/inventory.compute.gcp.yml"
  global gcp_inventory
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
  gcp_inventory.fa.set_block_style()
  with open(ansible_gcp_file, "w") as file:
    try:
      y = YAML()
      y.explicit_start = True
      y.default_flow_style = False
      y.dump(gcp_inventory, file)
    except:
      print("Failed to write gcp inventory file")
      exit(1)

  print("\nWriting gcp vars file...")
  gcp_vars_file = "ansible/gcp_vars.yml"
  gcp_vars = round_trip_load(str({
    "gcp_cred_kind": "serviceaccount", 
    "gcp_cred_file": service_account_file,
    "region": region_input,
    "zone": zone_input,
    "firewall_rule": "monkey-ansible-firewall",
  }))
  gcp_vars["gcp_ssh_private_key_path"] = details["gcp_ssh_private_key_path"]
  gcp_vars["gcp_storage_name"] = details["gcp_storage_name"]
  gcp_vars["monkeyfs_path"] = details["monkeyfs_path"]


  gcp_vars.fa.set_block_style()
  with open(gcp_vars_file, "w") as file:
    try:
      y = YAML()
      y.explicit_start = True
      y.default_flow_style = False
      y.dump(gcp_vars, file)
    except:
      print("Failed to write gcp inventory file")
      exit(1)
  setup_gcp_monkeyfs()

def setup_gcp_monkeyfs():
  print("\nSetting up monkeyfs...")
  print(os.getcwd())
  monkeyfs_path = os.path.join(os.getcwd(), "ansible/monkeyfs")
  runner = ansible_runner.run(playbook='gcp_install_fs.yml', 
                              private_data_dir='ansible',
                              extravars={
                                        "core_monkeyfs_path": monkeyfs_path
                                    },
                              quiet=False)
  events = [e for e in runner.events]
  monkeyfs_path = events[len(events)-2]["event_data"]["res"]["msg"]
  if len(runner.stats.get("failures")) != 0:
    print("Failed installing and setting up monkeyfs")
    exit(1)
  print("Successfully installed and setup monkeyfs\nPath:", monkeyfs_path)
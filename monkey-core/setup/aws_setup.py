import os
from ruamel.yaml import YAML, round_trip_load
import ansible_runner

def create_aws_provider(provider_name, yaml, args):
  details = round_trip_load(str({
    "name": provider_name,
    "type": "aws",
    # "project": "",
    # "gcp_cred_kind": "serviceaccount",
    # "gcp_cred_file": "",
  }))
  region_input = args.region or "us-east-1"
  zone_input = args.zone or region_input + "-b"
  if args.noinput == False:
    region_input = input("Set aws region (us-east-1): ")
    zone_input = input("Set aws region ({}): ".format(region_input + "-b")) or region_input + "-b"
  
  details["aws_region"] = region_input
  details["aws_zone"] = zone_input
  
  details["gcp_ssh_private_key_path"] = None #  "  # Defaults to keys/gcp"
  details.yaml_set_comment_before_after_key("gcp_ssh_private_key_path", before="\n\n###########\n# Optional\n###########")
  details.yaml_add_eol_comment("Defaults to keys/gcp", "gcp_ssh_private_key_path")
  details["storage_name"] = None #  "  # Defaults to monkeyfs"
  details.yaml_add_eol_comment("Defaults to monkeyfs", "storage_name")
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
  aws_vars_file = "ansible/gcp_vars.yml"
  aws_vars = round_trip_load(str({
    "aws_region": region_input,
    "aws_zone": zone_input,
    "firewall_rule": "monkey-ansible-firewall",
  }))
  aws_vars["aws_storage_name"] = details["aws_storage_name"]
  aws_vars["monkeyfs_path"] = details["monkeyfs_path"]


  aws_vars.fa.set_block_style()
  with open(aws_vars_file, "w") as file:
    try:
      y = YAML()
      y.explicit_start = True
      y.default_flow_style = False
      y.dump(aws_vars, file)
    except:
      print("Failed to write gcp inventory file")
      exit(1)
  setup_gcp_monkeyfs()

def setup_gcp_monkeyfs():
  print("\nSetting up monkeyfs...")
  print(os.getcwd())
  monkeyfs_path = os.path.join(os.getcwd(), "ansible/monkeyfs-gcp")
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
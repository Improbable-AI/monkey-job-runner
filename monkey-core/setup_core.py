import os
import io
import readline
from ruamel.yaml import YAML, round_trip_load

from setup.gcp_setup import create_gcp_provider
from setup.utils import Completer, get_file_path

comp = Completer()
# we want to treat '/' as part of a word, so override the delimiters
readline.set_completer_delims(' \t\n;')
readline.parse_and_bind("tab: complete")
readline.set_completer(comp.complete)




if __name__ == "__main__":
  print("Initializing Monkey Core...")
  try:
    with open(r'providers.yml') as file:
      provider_yaml = YAML().load(file)
  except:
    print("No providers.yml file found")
    provider_yaml = round_trip_load("---\nproviders: []")

  print(provider_yaml)
  providers = provider_yaml.get("providers", [])
  if providers is None:
    providers = []
  print(providers)

  print("{} providers found: {}".format(len(providers), ", ".join([x.get("name", "unknown") for x in providers])))

  create = input("Create a new provider? (y/N): ")
  if create.lower() in ["y", "yes"]:
    print("Creating New Provider...")
    
    provider_type = input("Provider type? (gcp, local, aws) : ")
    provider_name = None
    if "gcp" == provider_type:
      provider_name = "gcp"
    elif "aws" == provider_type:
      provider_name = "aws"
      print("Currently unsupported provider type")
      exit(1)
    elif "local" == provider_type:
      provider_name = "local"
      print("Currently unsupported provider type")
      exit(1)
    else:
      print("Unsupported provider type")
      exit(1)

    for p in [x.get("type", "unknown") for x in providers]:
      if p == provider_type:
        print("Currently only one provider of each type is supported")
        exit(1)
    
    c = ""
    while provider_name + c in [x.get("name", "unknown") for x in providers]:
      if c == "":
        c = "2"
      else:
        c = str(int(c) + 1)
    provider_name = provider_name + c

    provider_name = input("Provider name? ({}) : ".format(provider_name)) or provider_name
    
    print("Creating {}, type: {}".format(provider_name, provider_type))

    if "gcp" == provider_type:
      p = create_gcp_provider(provider_name, provider_yaml)
    elif "aws" == provider_type:
      print("Currently unsupported provider type")
      exit(1)
    elif "local" == provider_type:
      print("Currently unsupported provider type")
      exit(1)
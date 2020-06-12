import os
import io
import readline
from ruamel.yaml import YAML, round_trip_load

from setup.gcp_setup import create_gcp_provider, setup_gcp_monkeyfs
from setup.utils import Completer, get_monkey_fs

import argparse



comp = Completer()
# we want to treat '/' as part of a word, so override the delimiters
readline.set_completer_delims(' \t\n;')
readline.parse_and_bind("tab: complete")
readline.set_completer(comp.complete)

def parse_args():
  parser = argparse.ArgumentParser(description='Check for flags.')
  parser.add_argument('-n', '--noinput', action='store_true', required=False,
                      help='Run setup and skips input where possible (you must pass all requried params)')

  parser.add_argument('-c','--create', action='store_true', required=False, default=False,
                      help='Create a new provider')

  parser.add_argument('--type', dest='provider_type', required=False, default=None,
                      help='Allows you to pass provider type')
  parser.add_argument('--name', dest='provider_name', required=False, default=None,
                      help='Allows you to pass provider name')

  parser.add_argument('-i','--identification-file', dest='identification_file', required=False, default=None,
                      help='Allows you to pass the key filepath')

  parser.add_argument('--region', dest='region', required=False, default=None,
                      help='Allows you to pass provider region (gcp: Required, default: us-east-1)')
  parser.add_argument('--zone', dest='zone', required=False, default=None,
                      help='Allows you to pass provider zone (gcp: Required, default: us-east-1)')
  
  parser.add_argument('--filesystem-only', action='store_true', required=False,
                      help='Run setup and only configures the local shared filesystem')
  args = parser.parse_args()
  return args

def main():
  print("Initializing Monkey Core...")
  try:
    with open(r'providers.yml') as file:
      provider_yaml = YAML().load(file)
  except:
    print("No providers.yml file found")
    provider_yaml = round_trip_load("---\nproviders: []")
  providers = provider_yaml.get("providers", [])
  if providers is None:
    providers = []

  print("{} providers found: {}".format(len(providers), ", ".join([x.get("name", "unknown") for x in providers])))
  args = parse_args()

  monkeyfs = get_monkey_fs()
  if monkeyfs is None:
    print("No monkeyfs path configured")
    create = "y"
    if args.noinput == False:
      create = input("Would you like to create a gcp monkeyfs? (Y/n): ") or create
      create = create.lower() in ["y", "yes"]
    if create:
      print("Creating New GCP MonkeyFS...")
      setup_gcp_monkeyfs()
  else:
    print("Found monkeyfs: {}".format(monkeyfs))
  
  provider_name = args.provider_name
  provider_type = args.provider_type
 
  if args.filesystem_only:
    if "gcp" in [x.get("type", "unknown") for x in providers]:
      setup_gcp_monkeyfs()
    exit(0)
  create = args.create
  if args.noinput == False:
    create = input("Create a new provider? (y/N): ")
    create = create.lower() in ["y", "yes"]
  if create:
    print("Creating New Provider...")
    
    provider_type = args.provider_type
    if args.noinput == False:
      provider_type = input("Provider type? (gcp, local, aws) : ")
    
    provider_name = args.provider_name
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
      print("Unsupported provider type: '{}'".format(provider_type))
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

    if args.provider_name is not None and args.provider_name not in [x.get("name", "unknown") for x in providers]:
      provider_name = args.provider_name
    if args.noinput == False:
      provider_name = input("Provider name? ({}) : ".format(provider_name)) or provider_name
    
    print("Creating {}, type: {}".format(provider_name, provider_type))

    if "gcp" == provider_type:
      p = create_gcp_provider(provider_name, provider_yaml, args)
    elif "aws" == provider_type:
      print("Currently unsupported provider type")
      exit(1)
    elif "local" == provider_type:
      print("Currently unsupported provider type")
      exit(1)

  return 0

if __name__ == "__main__":
  exit(main())
  
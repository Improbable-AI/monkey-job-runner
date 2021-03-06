#!/usr/bin/env python3
import argparse
import io
import os
import readline

from ruamel.yaml import YAML, round_trip_load
from termcolor import colored, cprint

from core.setup_scripts.aws_setup import (check_aws_provider,
                                          create_aws_provider)
from core.setup_scripts.gcp_setup import (check_gcp_provider,
                                          create_gcp_provider)
from core.setup_scripts.local_setup import (check_local_provider,
                                            create_local_provider)
from core.setup_scripts.mongo_utils import get_monkey_db
from core.setup_scripts.utils import Completer

comp = Completer()
# we want to treat '/' as part of a word, so override the delimiters
readline.set_completer_delims(' \t\n;')
if 'libedit' in readline.__doc__:
    readline.parse_and_bind("bind ^I rl_complete")
else:
    readline.parse_and_bind("tab: complete")
readline.set_completer(comp.complete)


def add_provider_general_args(parser):
    parser.add_argument(
        '--noinput',
        action='store_true',
        required=False,
        help=
        'Run setup and skips input where possible (you must pass all requried params)'
    )

    parser.add_argument('-c',
                        '--create',
                        action='store_true',
                        required=False,
                        default=False,
                        help='Create a new provider')

    parser.add_argument('--type',
                        dest='provider_type',
                        required=False,
                        default=None,
                        help='Allows you to pass provider type')
    parser.add_argument('--name',
                        dest='provider_name',
                        required=False,
                        default=None,
                        help='Allows you to pass provider name')

    parser.add_argument('-i',
                        '--identification-file',
                        dest='identification_file',
                        required=False,
                        default=None,
                        help='Allows you to pass the key filepath')
    parser.add_argument('--ssh-key-name',
                        dest='ssh_key_name',
                        required=False,
                        default=None,
                        help='Allows you to name your generated ssh-key')


def add_provider_local_args(parser):
    parser.add_argument('--local-host',
                        dest='local_hosts',
                        action="append",
                        required=False,
                        default=[],
                        nargs="+",
                        help='Allows you to add local hosts with no input')

    parser.add_argument(
        '--monkeyfs-path',
        dest='monkeyfs_path',
        required=False,
        default=None,
        help='The path to use to mount the shared filesystem on hosts')
    parser.add_argument(
        '--monkeyfs-scratch',
        dest='monkeyfs_scratch',
        required=False,
        default=None,
        help='The path to use as scratch space on worker nodes')
    parser.add_argument(
        '--monkeyfs-public-ip',
        dest='monkeyfs_public_ip',
        required=False,
        default=None,
        help='The public ip of the master node (workers use this ip)')
    parser.add_argument(
        '--monkeyfs-public-port',
        dest='monkeyfs_public_port',
        required=False,
        default=None,
        help='The  ssh port of the master node (workers use this ssh port)')
    parser.add_argument(
        '--local-instances-file',
        dest='local_instances_file',
        required=False,
        default=None,
        help='The file to store static local instance information')

    parser.add_argument(
        '--localhost-only',
        dest='localhost_only',
        required=False,
        action="store_true",
        default=False,
        help='Used only if the core and worker noder are localhost (CI)')


def add_provider_cloud_args(parser):
    parser.add_argument(
        '--region',
        dest='region',
        required=False,
        default=None,
        help='Allows you to pass provider region (default: us-east-1)')
    parser.add_argument(
        '--zone',
        dest='zone',
        required=False,
        default=None,
        help='Allows you to pass provider zone (default: us-east-1)')
    parser.add_argument(
        '--storage-name',
        dest='storage_name',
        required=False,
        default=None,
        help=
        'Allows you to pass a specific bucket name (default: monkeyfs-XXXXXXX)'
    )
    parser.add_argument(
        '--filesystem-only',
        action='store_true',
        required=False,
        help='Run setup and only configures the local shared filesystem')


def parse_args():
    parser = argparse.ArgumentParser(description='Check for flags.')
    add_provider_general_args(parser)
    add_provider_local_args(parser)
    add_provider_cloud_args(parser)
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
    if provider_yaml is None:
        provider_yaml = round_trip_load("---\nproviders: []")
    providers = provider_yaml.get("providers", [])
    if providers is None:
        providers = []

    print("{} providers found: {}".format(
        len(providers),
        ", ".join([x.get("name", "unknown") for x in providers])))
    args = parse_args()

    if len(providers) > 0:
        print("Checking integrity of existing providers...")
    for provider in providers:
        provider_type = provider.get("type", None)
        if provider_type == "gcp":
            check_gcp_provider(provider)
        elif provider_type == "aws":
            check_aws_provider(provider)
        else:
            print("Unsupported provider type", provider_type)

    provider_name = args.provider_name
    provider_type = args.provider_type

    create = args.create
    if not args.noinput and not args.create:
        create = input("Create a new provider? (Y/n): ")
        create = create.lower() not in ["n", "no"]
    if create:
        print("Creating New Provider...")

        if not args.noinput and args.provider_type is None:
            provider_type = input("Provider type? (gcp, local, aws) : ")

        if provider_type not in ["gcp", "aws", "local"]:
            print("Unsupported provider type: '{}'".format(provider_type))
            exit(1)

        for p in [x.get("type", "unknown") for x in providers]:
            if p == provider_type:
                print("Currently only one provider of each type is supported")
                exit(1)

        if provider_name is None:
            provider_name = provider_type
        c = ""
        while provider_name + c in [
                x.get("name", "unknown") for x in providers
        ]:
            if c == "":
                c = "2"
            else:
                c = str(int(c) + 1)
        provider_name = provider_name + c

        if args.provider_name is not None and args.provider_name not in [
                x.get("name", "unknown") for x in providers
        ]:
            provider_name = args.provider_name
        if not args.noinput and not args.provider_name:
            provider_name = input("Provider name? ({}) : ".format(
                provider_name)) or provider_name

        print("Creating {}, type: {}".format(provider_name, provider_type))

        if "gcp" == provider_type:
            success = create_gcp_provider(provider_name, provider_yaml, args)
            if success:
                print("Successfully created GCP Provider")
            else:
                print("Failed to create GCP Provider")
        elif "aws" == provider_type:
            success = create_aws_provider(provider_name, provider_yaml, args)
            if success:
                print("Successfully created AWS Provider")
            else:
                print("Failed to create AWS Provider")
        elif "local" == provider_type:
            success = create_local_provider(provider_name, provider_yaml, args)
            if success:
                print("Successfully created Local Provider")
            else:
                print("Failed to create Local Provider")

    # Make main monkeyfs dir
    os.makedirs("ansible/monkeyfs", exist_ok=True)
    db_connection_success = get_monkey_db()
    if db_connection_success:
        print("MonkeyDB connection successful!")
    else:
        print("No connection to MonkeyDB found. \n" +
              "Please ensure you start a MonkeyDB locally\n " +
              "To do so:\ndocker-compose start")

    return 0


if __name__ == "__main__":

    exit(main())

#!/usr/bin/env python3
import argparse
import io
import os
import readline

from ruamel.yaml import YAML, round_trip_load
from termcolor import colored, cprint

from setup_scripts.aws_setup import check_aws_provider, create_aws_provider
from setup_scripts.gcp_setup import check_gcp_provider, create_gcp_provider
from setup_scripts.local_setup import check_local_provider, create_local_provider
from setup_scripts.mongo_utils import get_monkey_db
from setup_scripts.utils import Completer, get_monkey_fs

comp = Completer()
# we want to treat '/' as part of a word, so override the delimiters
readline.set_completer_delims(' \t\n;')
readline.parse_and_bind("tab: complete")
readline.set_completer(comp.complete)


def parse_args():
    parser = argparse.ArgumentParser(description='Check for flags.')
    parser.add_argument(
        '-n',
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

    parser.add_argument(
        '--region',
        dest='region',
        required=False,
        default=None,
        help=
        'Allows you to pass provider region (gcp: Required, default: us-east-1)'
    )
    parser.add_argument(
        '--zone',
        dest='zone',
        required=False,
        default=None,
        help=
        'Allows you to pass provider zone (gcp: Required, default: us-east-1)')
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
    if args.noinput == False:
        create = input("Create a new provider? (Y/n): ")
        create = create.lower()  not in ["n", "no"]
    if create:
        print("Creating New Provider...")

        provider_type = args.provider_type
        if args.noinput == False:
            provider_type = input("Provider type? (gcp, local, aws) : ")
            provider_type = "local"

        provider_name = args.provider_name
        if "gcp" == provider_type:
            provider_name = "gcp"
        elif "aws" == provider_type:
            provider_name = "aws"
        elif "local" == provider_type:
            provider_name = "local"
        else:
            print("Unsupported provider type: '{}'".format(provider_type))
            exit(1)

        for p in [x.get("type", "unknown") for x in providers]:
            if p == provider_type:
                print("Currently only one provider of each type is supported")
                exit(1)

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
        if args.noinput == False:
            provider_name = input("Provider name? ({}) : ".format(
                provider_name)) or provider_name

        print("Creating {}, type: {}".format(provider_name, provider_type))

        if "gcp" == provider_type:
            create_gcp_provider(provider_name, provider_yaml, args)
        elif "aws" == provider_type:
            create_aws_provider(provider_name, provider_yaml, args)
        elif "local" == provider_type:
            create_local_provider(provider_name, provider_yaml, args)

    db_connection_success = get_monkey_db()
    if db_connection_success:
        print("MonkeyDB connection successful!")
    else:
        print(
            "No connection to MonkeyDB found. \nPlease ensure you start a MonkeyDB locally\nTo do so:\ndocker-compose start"
        )

    return 0


if __name__ == "__main__":

    exit(main())

#!/usr/bin/env python
import argparse
import sys
from cmd import Cmd

import yaml
from termcolor import colored

import monkeycli.core_info
import monkeycli.core_job
import monkeycli.parsers
from monkeycli.globals import MONKEY_CORE_URL
from monkeycli.monkeycli_init import init_runfile


class MonkeyCLI(Cmd):

    prompt = 'monkey> '

    def __init__(self):
        super().__init__()
        if len(sys.argv) > 1:
            self.parse_args(sys.argv[1:])
            exit(0)

    def do_exit(self, inp):
        '''exit the application.'''
        print("Bye")
        return True

    def do_help(self, inp):
        self.parse_args(["--help"])

    def default(self, inp):
        if inp == 'x' or inp == 'q':
            return self.do_exit(inp)

        print("Default: {}".format(inp))
        self.parse_args(inp.split(" "))

    # def create_instance(self, provider, machine_overrides):
    #     print("Creating Instance with override args:\n{}".format(
    #         machine_overrides))
    #     return self.monkey.create_instance(provider=provider,
    #                                        machine_params=machine_overrides)

    def list_providers(self, printout=False):
        return monkeycli.core_info.list_providers(printout)

    def list_instances(self, args, printout=False):
        return monkeycli.core_info.list_instances(args, printout)

    def list_jobs(self, args, printout=False):
        return monkeycli.core_info.list_jobs(args, printout)

    def check_or_upload_dataset(self,
                                dataset,
                                provider_name,
                                compression_type="tar"):
        return monkeycli.core_job.check_or_upload_dataset(
            dataset, provider_name, compression_type)

    def upload_persisted_folder(self, persist, job_uid, provider_name):
        return monkeycli.core_job.upload_persisted_folder(
            persist, job_uid, provider_name)

    def upload_codebase(self, code, job_uid, provider_name):
        return monkeycli.core_job.upload_codebase(code, job_uid, provider_name)

    def submit_job(self, job):
        return monkeycli.core_job.submit_job(job)

    def get_job_uid(self):
        return monkeycli.core_info.get_job_uid()

    def run_job(self,
                cmd,
                job_yaml_file="job.yml",
                job_uid=None,
                foreground=False,
                provider=None,
                printout=False):
        if printout:
            print("\nMonkey running:\n{}".format(colored(cmd, "green")))

        # Parse job.yml
        try:
            with open(job_yaml_file, 'r') as job_file:
                job_yaml = yaml.load(job_file, Loader=yaml.FullLoader)
        except:
            print("Unable to parse job.yml, path: {}".format(job_yaml_file))
            raise ValueError("Could not read job file")

        # Get provider
        if len(job_yaml["providers"]) == 0:
            raise ValueError("You must add a provider to the job.yml")
        if provider is not None:
            if provider in [x["name"] for x in job_yaml["providers"]]:
                job_yaml["provider"] = provider
            else:
                raise ValueError("The specified provider ")
        else:
            job_yaml["provider"] = job_yaml["providers"][0]["name"]
        provider = job_yaml["provider"]
        print("Running on provider: {}".format(provider))

        if job_uid is None:
            job_uid = self.get_job_uid()
        job_yaml["job_uid"] = job_uid
        job_yaml["cmd"] = cmd
        print("Creating job with id: ", colored(job_uid, "green"), "\n")

        # Check Data
        for dataset in job_yaml.get("data", []):
            dataset_checksum, dataset_filename = self.check_or_upload_dataset(
                dataset=dataset, provider_name=provider)
            dataset["dataset_checksum"] = dataset_checksum
            dataset["dataset_filename"] = dataset_filename

        # Upload persisted folder
        for persist_dir in job_yaml.get("persist", []):
            self.upload_persisted_folder(persist=persist_dir,
                                         job_uid=job_uid,
                                         provider_name=provider)

        # Upload codebase
        if "code" not in job_yaml:
            print("Please define your codebase in the yaml")
            raise ValueError("code undefined in job.yml")

        # Setup extra job args
        job_yaml["foreground"] = foreground

        self.upload_codebase(code=job_yaml["code"],
                             job_uid=job_uid,
                             provider_name=provider)

        # Submit job
        self.submit_job(job=job_yaml)

    def run(self, cmd):
        print(["run"] + cmd.split(" "))
        self.parse_args(["run"] + cmd.split(" "), printout=True)

    def parse_args(self, input_args, printout=True):
        print("Parsing args: {}\n".format(input_args))
        parser = argparse.ArgumentParser(description='Parses monkey commands')

        subparser = parser.add_subparsers(help="Monkey Commands",
                                          dest="command")

        run_parser = monkeycli.parsers.get_run_parser(subparser=subparser)

        create_parser, create_subparser = monkeycli.parsers.get_create_parser(
            subparser=subparser)

        list_parser, list_subparser = monkeycli.parsers.get_list_parser(
            subparser=subparser)

        info_parser = subparser.add_parser("info",
                                           help="Info on the specified item")
        info_subparser = info_parser.add_subparsers(description="Info options",
                                                    dest="info_option")
        # info_jobs_parser = list_subparser.add_parser(
        #     "job", help="Gets the info on the specified job")
        # info_providers_parser = list_subparser.add_parser(
        #     "instance", help="List the info of the specified instance")

        init_parser = monkeycli.parsers.get_empty_parser(
            subparser=subparser,
            name="init",
            helptext=
            "Run this command to instantiate the monkey cli with a job.yml file for your workload"
        )
        help_parser = monkeycli.parsers.get_empty_parser(
            subparser=subparser,
            name="help",
            helptext="Lists commands and options available")

        try:
            args, remaining_args = parser.parse_known_args(input_args)
        except:
            return False

        if args.command == "run":
            return self.run_job(cmd=" ".join(remaining_args),
                                job_yaml_file=args.job_yaml_file,
                                job_uid=args.job_uid,
                                foreground=args.foreground,
                                provider=args.provider,
                                printout=printout)
        elif args.command == "create":
            if args.create_option == "instance":
                additional_args = dict()
                provider = args.provider
                if len(remaining_args):
                    print("Adding override argumen: \n")
                for i in range(0, len(remaining_args), 2):
                    if remaining_args[i][:2] == "--":
                        print("{}={}".format(remaining_args[i][2:],
                                             remaining_args[i + 1]))
                        additional_args[remaining_args[i]
                                        [2:]] = remaining_args[i + 1]

                return self.create_instance(provider=args.provider,
                                            machine_overrides=additional_args)
            else:
                create_parser.print_help()
                return False
        elif args.command == "list":
            if args.list_option == "jobs":
                return self.list_jobs(args=vars(args), printout=printout)
            elif args.list_option == "instances":
                return self.list_instances(args=vars(args), printout=printout)
            elif args.list_option == "providers":
                return self.list_providers(printout=printout)
            else:
                list_parser.print_help()
                return False
        elif args.command == "init":
            return init_runfile()
        elif args.command == "help":
            parser.print_help()
            return False
        else:
            parser.print_help()
            return False

        return args

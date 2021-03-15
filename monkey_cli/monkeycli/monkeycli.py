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

    def list_command(self, list_parser, args, printout=False):
        if args.list_option == "jobs":
            return monkeycli.core_info.list_jobs(vars(args), printout)
        if args.list_option == "instances":
            return monkeycli.core_info.list_instances(vars(args), printout)
        if args.list_option == "providers":
            return monkeycli.core_info.list_providers(printout)
        list_parser.print_help()
        return False

    def info_command(self, info_parser, args, printout=False):
        print(args)
        print()
        if args.info_option == "jobs" or args.info_option == "job":
            return monkeycli.core_info.info_jobs(job_uids=args.job_uids,
                                                 printout=printout)
        if args.info_option == "providers":
            return monkeycli.core_info.info_provider(provider=args.provider,
                                                     printout=printout)
        info_parser.print_help()
        return False

    def output_command(self, output_parser, args, printout=False):
        print(args)
        return monkeycli.core_info.job_output(job_uid=args.job_uid,
                                              printout=printout)

    def check_or_upload_dataset(self,
                                dataset,
                                provider_name,
                                compression_type="tar"):
        return monkeycli.core_job.check_or_upload_dataset(
            dataset, provider_name, compression_type)

    def upload_persisted_folder(self, persist, job_uid, provider_name):
        return monkeycli.core_job.upload_persisted_folder(
            persist, job_uid, provider_name)

    def check_or_upload_codebase(self, code, job_uid, run_name, provider_name):
        return monkeycli.core_job.check_or_upload_codebase(
            code=code,
            job_uid=job_uid,
            run_name=run_name,
            provider_name=provider_name)

    def submit_job(self, job):
        return monkeycli.core_job.submit_job(job)

    def get_new_job_uid(self):
        return monkeycli.core_info.get_new_job_uid()

    def run_job(self, cmd, args, printout=False):
        job_yaml_file = args.job_yaml_file
        foreground = args.foreground
        provider = args.provider
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
                raise ValueError("The specified provider was not found")
        else:
            job_yaml["provider"] = job_yaml["providers"][0]["name"]
        provider = job_yaml["provider"]
        print("Running on provider: {}".format(provider))
        all_providers = monkeycli.core_info.list_providers()
        print(all_providers)
        found_remote_provider = None
        for remote_provider in all_providers:
            if remote_provider.get("name", "") == provider:
                found_remote_provider = remote_provider

        if found_remote_provider is None:
            raise ValueError(
                "Unable to find the specified provider on Monkey Core")
        if found_remote_provider.get("type", "") == "local":
            # Check for defined instance
            instance = args.instance
            print(f"Running on instance: {instance}")
            available_instances = ", ".join(
                monkeycli.core_info.list_local_instances())
            print("Available instances", available_instances)
            if instance is None:
                raise ValueError(
                    "Please define an instance to run on the local provider. "
                    +
                    f"\nAvailable instance include: \n{available_instances}" +
                    "\nTo run with instance set use monkey run -i <instance_name>"
                )
            job_yaml["instance"] = args.instance

        job_uid = self.get_new_job_uid()
        job_yaml["job_uid"] = job_uid
        job_yaml["cmd"] = cmd
        print("Creating job with id: ", colored(job_uid, "green"), "\n")

        run_name = job_yaml["project_name"] + "-" + job_yaml["name"]

        # Check Data
        data_yaml = job_yaml.get("data", None)
        if data_yaml is not None and type(data_yaml) is not list:
            data_yaml = [data_yaml]

        for dataset in data_yaml:
            checksum, extension = self.check_or_upload_dataset(
                dataset=dataset, provider_name=provider)
            dataset["checksum"] = checksum
            dataset["extension"] = extension

        job_yaml["data"] = data_yaml

        # Upload persisted folder
        for persist_dir in job_yaml.get("persist", []):
            self.upload_persisted_folder(persist=persist_dir,
                                         job_uid=job_uid,
                                         provider_name=provider)

        # Upload codebase
        code_yaml = job_yaml.get("code", None)
        if code_yaml is None:
            print("Please define your codebase in the yaml")
            raise ValueError("code undefined in job.yml")

        if code_yaml is not None and type(code_yaml) is not list:
            code_yaml = [code_yaml]

        for codebase in code_yaml:
            codebase_params = self.check_or_upload_codebase(
                code=job_yaml["code"],
                job_uid=job_uid,
                run_name=run_name,
                provider_name=provider)
            codebase["checksum"] = codebase_params["checksum"]
            codebase["extension"] = codebase_params["extension"]
            codebase["run_name"] = codebase_params["run_name"]
        job_yaml["code"] = code_yaml

        # Setup extra job args
        job_yaml["foreground"] = foreground

        print(job_yaml)
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

        info_parser = monkeycli.parsers.get_info_parser(subparser=subparser)

        output_parser = monkeycli.parsers.get_output_parser(
            subparser=subparser)

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
                                args=args,
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
            self.list_command(list_parser=list_parser,
                              args=(args),
                              printout=printout)
        elif args.command == "info":
            return self.info_command(info_parser=info_parser,
                                     args=(args),
                                     printout=printout)
        elif args.command == "output":
            return self.output_command(output_parser=output_parser,
                                       args=(args),
                                       printout=printout)
        elif args.command == "init":
            return init_runfile()
        elif args.command == "help":
            parser.print_help()
            return False
        else:
            parser.print_help()
            return False

        return args

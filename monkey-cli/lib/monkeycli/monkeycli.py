#!/usr/bin/env python
import time
import argparse
import sys
import json
from cmd import Cmd
import requests
import yaml
MONKEY_CORE_URL = "http://localhost:9990/"
from checksumdir import dirhash
from urllib.parse import urljoin
import tempfile
import os
import shutil

class MonkeyCLI(Cmd):

    prompt = 'monkey> '

    def build_url(self, path):
        return urljoin(MONKEY_CORE_URL, path.strip("/"))

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

    def create_instance(self, provider, machine_overrides):
        print("Creating Instance with override args:\n{}".format(machine_overrides))
        return self.monkey.create_instance(provider= provider, machine_params=machine_overrides)        

    def list_providers(self, printout=False):
        providers = []
        r = requests.get(self.build_url("list/providers"))
        if printout:
            print("Listing Providers available")
            print("\n".join(r.json()))
            print("Total: {}".format(len(r.json())))
        return r.json()

    def list_instances(self, providers, printout=False):
        r = requests.get(self.build_url("list/instances"), params={"providers": providers})
        if printout:
            res = r.json()
            print("Listing Instances available\n")
            for key, value in res.items():
                print("Instance list for: {}".format(key))
                for inst in value:
                    print("Name: {}, IP: {}, State: {}".format(inst["name"], inst["ip_address"], inst["state"]))
                print("Total: {}\n".format(len(value)))
        return r.json()

    def list_jobs(self, providers, printout=False):
        r = requests.get(self.build_url("list/jobs"), params={"providers": providers})
        if printout:
            res = r.json()
            print("Listing Jobs available")
            for key, value in res.items():
                print("Job list for: {}".format(key))
                print("\n".join(value))
                print("Total: {}".format(len(value)))
        return r.json()

    def check_or_upload_dataset(self, dataset):
        dataset_name = dataset["name"]
        dataset_path = dataset["path"]
        dataset_checksum = dirhash(dataset_path)
        print("Dataset checksum: {}".format(dataset_checksum))
        compression_type = "tar"
        compression_suffix = ".tar"
        if dataset.get("compression", None) is not None:
            compression_map = {"tar": ".tar", "gztar":".tar.gz", "zip":".zip"}
            compression_type = dataset["compression"]
            compression_suffix = compression_map[compression_type]
        
        dataset_params = {
            "dataset_name": dataset_name,
            "dataset_checksum": dataset_checksum,
            "dataset_path": dataset_path,
            "dataset_extension": compression_suffix
        }
        r = requests.get(self.build_url("check/dataset"), params= dataset_params)
        dataset_found, msg = r.json().get("found", False), r.json().get("msg", "")
        print(msg)
        if dataset_found == False:
            with tempfile.NamedTemporaryFile() as dir_tmp:
                print("Compressing Dataset")
                shutil.make_archive(dir_tmp.name, compression_type, dataset_path)
                compressed_name = dir_tmp.name + compression_suffix
                print(compressed_name)
                try:
                    with open(compressed_name, "rb") as compressed_dataset:
                        r = requests.post(self.build_url("upload/dataset/"),
                                        data=compressed_dataset,
                                        params=dataset_params, 
                                        allow_redirects=True)
                        success = r.json()["success"]
                        print("Upload Dataset Success: ", success)
                except:
                    print("Upload failure")
                finally:
                    os.remove(compressed_name)
        


    def run_job(self, cmd, job_yaml_file="job.yml", printout=False):
        if printout:
            print("\nMonkey running:\n{}".format(cmd))

        # Parse job.yml
        try:
            with open(job_yaml_file, 'r') as job_file:
                job_yaml = yaml.load(job_file, Loader=yaml.FullLoader)
        except:
            print("Unable to parse job.yml, path: {}".format(job_yaml_file))
            raise ValueError("Could not read job file")

        # Check Data
        for dataset in job_yaml.get("data", []):
            print("\nChecking for dataset: {}".format(dataset["name"]))
            self.check_or_upload_dataset(dataset=dataset)




    def get_list_parser(self, subparser):
        list_parser = subparser.add_parser("list", help="List jobs on the specified provider")
        list_subparser = list_parser.add_subparsers(description="List command options", dest="list_option")
        list_jobs_parser = list_subparser.add_parser("jobs", help="List the jobs on the given provider")
        list_providers_parser = list_subparser.add_parser("providers", help="List the jobs on the given provider")
        list_instances_parser = list_subparser.add_parser("instances", help="List the jobs on the given provider")
        list_jobs_parser.add_argument('-p','--provider', dest='providers', type=str, required=False, default=[],
                         help='The provider you wish to use.  Should be defined in providers.yml')
        list_instances_parser.add_argument('-p','--provider', dest='providers', type=str, required=False, default=[],
                         help='The provider you wish to use.  Should be defined in providers.yml')
        return list_parser, list_subparser
    
    def get_create_parser(self, subparser):
        create_parser = subparser.add_parser("create", help="Create an instance on the specified provider")
        create_subparser = create_parser.add_subparsers(description="Create command options", dest="create_option")
        create_instance_parser = create_subparser.add_parser("instance", help="Creates an instance with given provider and overrides")
        create_instance_parser.add_argument('-p','--provider', dest='provider', type=str, required=True,
                         help='The provider you wish to use.  Should be defined in cloud_providers.yml')
        # create_instance_parser.add_argument('machine_params', type=str, nargs=argparse.REMAINDER,
        #                  help='Any other machine overrides to replace values found in providers.yml')
        return create_parser, create_subparser

    def parse_args(self, input_args, printout=True):
        print("Parsing args: {}".format(input_args))
        parser = argparse.ArgumentParser(description='Parses monkey commands')

        subparser = parser.add_subparsers(help="Monkey Commands", dest="command")

        run_parser = subparser.add_parser("run", help="Run a job on the specified provider")
        run_parser.add_argument("--job_file","-j", required=False, default="job.yml", dest="job_yaml_file", 
                                help="Optionial specification of job.yml file")
        
        create_parser, create_subparser = self.get_create_parser(subparser=subparser)

        list_parser, list_subparser = self.get_list_parser(subparser=subparser)

        info_parser = subparser.add_parser("info", help="Infoon the specified item")
        info_subparser = info_parser.add_subparsers(description="Info options", dest="info_option")
        info_jobs_parser = list_subparser.add_parser("job", help="Gets the info on the specified job")
        info_providers_parser = list_subparser.add_parser("instance", help="List the info of the specified instance")


        try:
            args, remaining_args = parser.parse_known_args(input_args)
        except:
            return False
        if args.command == "run":
            return self.run_job(cmd=" ".join(remaining_args), job_yaml_file=args.job_yaml_file, printout=printout)
            pass
        elif args.command == "create":
            if args.create_option == "instance":
                additional_args = dict()
                provider = args.provider
                if len(remaining_args):
                    print("Adding override argumen: \n")
                for i in range(0, len(remaining_args), 2):
                    if remaining_args[i][:2] == "--":
                        print("{}={}".format(remaining_args[i][2:], remaining_args[i + 1]))
                        additional_args[remaining_args[i][2:]] = remaining_args[i+1]
                
                return self.create_instance(provider=args.provider, machine_overrides=additional_args)
            else:
                create_parser.print_help()
                return False
        elif args.command == "list":
            if args.list_option == "jobs":
                raise NotImplementedError("Not implemented yet")
                return self.list_jobs(providers=args.providers, printout=printout)
            elif args.list_option == "instances":
                return self.list_instances(providers=args.providers, printout=printout)
            elif args.list_option == "providers":
                return self.list_providers(printout=printout)
            else:
                list_parser.print_help()
                return False
        else:
            parser.print_help()
            return False

        return args

def main():
    MonkeyCLI().cmdloop()

    return 0

if __name__ == "__main__":
    exit(main())
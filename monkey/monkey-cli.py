#!/usr/bin/env python
from monkey import Monkey
import time
import argparse
import sys


class MonkeyCLI():

    monkey = Monkey()

    def __init__(self):
        super().__init__()

    def ingest(self):
        self.parse_args(input_args=sys.argv)

    def run(self, input_args):
        print("Running")
        print(input_args)
        # parser.add_argument('-p','--provider', dest='provider', type=str, required=True,
        #                 help='The provider you wish to use.  Should be defined in cloud_providers.yaml')
        pass

    def list(self, input_args):
        print("Listing")
        print(input_args)
        parser = argparse.ArgumentParser(description='Monkey list commands')

    def list_providers(self):
        print('''
Listing Providers available
                ''')
        for handler in self.monkey.handlers:
            print("{}".format(handler))
        return True

    def parse_args(self, input_args):
        parser = argparse.ArgumentParser(description='Parses monkey commands')

        subparser = parser.add_subparsers(help="Monkey Commands", dest="command")

        run_parser = subparser.add_parser("run", help="Run a job on the specified provider")
        

        list_parser = subparser.add_parser("list", help="List jobs on the specified provider")
        list_subparser = list_parser.add_subparsers(description="List command options", dest="list_option")
        list_jobs_parser = list_subparser.add_parser("jobs", help="List the jobs on the given provider")
        list_providers_parser = list_subparser.add_parser("providers", help="List the jobs on the given provider")
        list_jobs_parser.add_argument('-p','--provider', dest='provider', type=str, required=True,
                         help='The provider you wish to use.  Should be defined in cloud_providers.yaml')
    
        args = parser.parse_args()
        if args.command == "run":
            pass
        elif args.command == "list":
            if args.list_option == "jobs":
                pass
            elif args.list_option == "providers":
                return self.list_providers()
                


        # parser.add_argument('command', help='Subcommand to run')
        # args = parser.parse_args(input_args[1:2])
        # if not hasattr(args, "command"):
        #     print('Unrecognized command')
        #     parser.print_help()
        #     exit(1)
        # # use dispatch pattern to invoke method with same name
        # print(getattr(args, "command"))
        # command = getattr(args, "command")
        # getattr(self, command)(input_args[2:])

        return args

def main():
    mcli = MonkeyCLI()
    mcli.ingest()

    return 0

if __name__ == "__main__":
    exit(main())
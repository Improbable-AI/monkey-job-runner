import argparse


def get_list_parser(subparser):
    list_parser = subparser.add_parser(
        "list", help="List jobs on the specified provider")
    list_subparser = list_parser.add_subparsers(
        description="List command options", dest="list_option")
    list_jobs_parser = list_subparser.add_parser(
        "jobs", help="List the jobs on the given provider")
    list_providers_parser = list_subparser.add_parser(
        "providers", help="List the jobs on the given provider")
    list_instances_parser = list_subparser.add_parser(
        "instances", help="List the jobs on the given provider")
    list_jobs_parser.add_argument(
        '-p',
        '--provider',
        dest='providers',
        type=str,
        required=False,
        default=[],
        help='The provider you wish to use.  Should be defined in providers.yml'
    )
    list_jobs_parser.add_argument('-n',
                                  '--num-jobs',
                                  dest='num_jobs',
                                  type=int,
                                  help='The number of jobs to display')
    return list_parser, list_subparser


def get_create_parser(subparser):
    create_parser = subparser.add_parser(
        "create", help="Create an instance on the specified provider")
    create_subparser = create_parser.add_subparsers(
        description="Create command options", dest="create_option")
    create_instance_parser = create_subparser.add_parser(
        "instance",
        help="Creates an instance with given provider and overrides")
    create_instance_parser.add_argument(
        '-p',
        '--provider',
        dest='provider',
        type=str,
        required=True,
        help=
        'The provider you wish to use.  Should be defined in cloud_providers.yml'
    )
    # create_instance_parser.add_argument('machine_params', type=str, nargs=argparse.REMAINDER,
    #                  help='Any other machine overrides to replace values found in providers.yml')
    return create_parser, create_subparser


def get_run_parser(subparser):
    run_parser = subparser.add_parser(
        "run", help="Run a job on the specified provider")

    run_parser.add_argument(
        "--provider",
        "-p",
        required=False,
        default=None,
        dest="provider",
        help=
        "Optionial specification of provider (Defaults to first listed provider)"
    )
    run_parser.add_argument("--job_file",
                            "-jf",
                            required=False,
                            default="job.yml",
                            dest="job_yaml_file",
                            help="Optionial specification of job.yml file")
    run_parser.add_argument(
        "--foreground",
        "-f",
        required=False,
        action='store_true',
        help="Run in foreground or detach when successfully sent")
    return run_parser


def get_info_parser(subparser):
    info_parser = subparser.add_parser("info",
                                       help="Get info on the specified item")
    info_subparser = info_parser.add_subparsers(
        description="Info command options", dest="info_option")

    info_jobs_parser = info_subparser.add_parser("job",
                                                 help="List the info of a job")
    info_jobs_parser.add_argument(
        "job_uids",
        default=[],
        nargs="+",
        help=
        "Get information about a job(s) (full specifier or three letter terminator)"
    )
    info_provider_parser = info_subparser.add_parser(
        "provider", help="List the info of a given provider")

    info_provider_parser.add_argument(
        "provider", help="Name of the provider to get info for")

    return info_parser


def get_output_parser(subparser):
    output_parser = subparser.add_parser("output",
                                         help="Get the output of a job")
    # output_subparser = output_parser.add_subparsers(
    #     description="Info command options", dest="output_option")

    output_parser.add_argument(
        "job_uid",
        help=
        "Get the output of a job (full specifier or three letter terminator)")

    return output_parser


def get_empty_parser(subparser, name, helptext):
    parser = subparser.add_parser(name, help=helptext)

    return parser


def get_init_parser(subparser):
    init_parser = subparser.add_parser(
        "init",
        help=
        "Run this command to instantiate the monkey cli with a job.yml file for your workload"
    )

    return init_parser

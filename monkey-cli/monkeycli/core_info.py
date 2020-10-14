import datetime

import requests
from termcolor import colored

from monkeycli.utils import build_url, human_readable_state


def get_job_uid():
    r = requests.get(build_url("get/job_uid"))
    return r.text


def list_jobs(args, printout=False):
    try:
        r = requests.get(build_url("list/jobs"), params=args)
    except:
        if printout:
            print("Unable to connect to Monkey Core: {}".format(
                build_url("list/jobs")))
            return []
    if printout:
        res = r.json()
        print("Listing Jobs available")

        job_dates = [(datetime.datetime.utcfromtimestamp(
            x["creation_date"]["$date"] / 1000.0), x) for x in res]
        job_dates = sorted(job_dates, reverse=True)
        header = colored("{:^26} {:^24} {:^19} {:^13} {:^13}".format(
            "Job Name", "Status", "Created", "Elapsed", "Runtime"),
                         attrs=["bold"])
        print("")
        print(header)
        date_format = "%m/%d/%y %H:%M"

        def print_time_delta(delta, timeunits=False):
            seconds = delta.total_seconds()
            if seconds > 3600:
                if timeunits:
                    return "{:02}h {:02}m {:02}s".format(
                        int(seconds // 3600), int((seconds % 3600) // 60),
                        int(seconds % 60))
                else:
                    return "{:02}:{:02}:{:02}".format(
                        int(seconds // 3600), int((seconds % 3600) // 60),
                        int(seconds % 60))
            elif seconds > 60:
                if timeunits:
                    return "{:02}m {:02}s".format(int((seconds % 3600) // 60),
                                                  int(seconds % 60))
                else:
                    return "{:02}:{:02}".format(int((seconds % 3600) // 60),
                                                int(seconds % 60))
            else:
                return "{:.1f}s".format(seconds)

        for date, job in job_dates:
            job_str = job["job_uid"].split("-")
            job_str[-1] = colored(job_str[-1], "green")
            job_str = "-".join(job_str)

            elapsed = print_time_delta(datetime.datetime.now() - date,
                                       timeunits=True)
            if job.get("completion_date", None) is not None:
                elapsed = print_time_delta(datetime.datetime.utcfromtimestamp(
                    job["completion_date"]["$date"] / 1000.0) - date,
                                           timeunits=True)

            runtime = print_time_delta(
                datetime.timedelta(seconds=job.get("run_elapsed_time", 0)),
                timeunits=True)
            line = "{:^35} {:^24} {:^19} {:^13} {:^13}".format(
                job_str, human_readable_state(job["state"]),
                date.strftime(date_format), elapsed, runtime)
            print(line)

    return r.json()


def list_providers(printout=False):
    try:
        r = requests.get(build_url("list/providers"))
    except:
        if printout:
            print("Unable to connect to Monkey Core: {}".format(
                build_url("list/providers")))
            return []
    response = r.json()["response"]
    if printout:
        print("Listing Providers available")
        print("\n\tTotal: {}".format((colored(len(response), "yellow"))))
        response_text = [
            "\n\tName: {} \tType: {}".format(colored(x["name"], "green"),
                                             colored(x["type"], "green"))
            for x in response
        ]
        print("\n".join(response_text))
        print("")
    return response


def list_instances(args, printout=False):
    try:
        r = requests.get(build_url("list/instances"), params=args)
    except:
        if printout:
            print("Unable to connect to Monkey Core: {}".format(
                build_url("list/instances")))
            return []
    if printout:
        res = r.json()
        print("Listing Instances available\n")
        header = colored("{:^26} {:^18} {:^17}".format("Instance Name",
                                                       "Public IP", "State"),
                         attrs=["bold"])
        print(header)
        print("")
        for key, value in res.items():
            provider_header = ("Instance list for: {}, Total: {}".format(
                colored(key, "green"), colored(len(value), "yellow")))
            provider_header = colored(provider_header, attrs=["bold"])
            print(provider_header)
            for inst in value:
                ip_address = inst.get("ip_address", None)
                if ip_address is None:
                    ip_address = "None"
                line = "{:^35} {:^18} {:^26}".format(
                    colored(inst["name"], "green"), ip_address,
                    colored(inst["state"], "yellow"))
                print(line)
    return r.json()

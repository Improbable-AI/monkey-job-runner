import datetime
import os
import tarfile

import requests
from requests import ConnectionError
from termcolor import colored

from monkeycli.utils import build_url, human_readable_state


class MonkeyCLIException(Exception):
    pass


class MonkeyCLIJobUIDException(MonkeyCLIException):
    pass


def get_request(url, **kwargs):
    try:
        r = requests.get(url, **kwargs)
    except ConnectionError:
        raise MonkeyCLIException("Unable to connect to monkey-core. " +
                                 "\nPlease ensure monkey-core is running")
    return r


def get_new_job_uid():
    r = requests.get(build_url("get/new_job_uid"))
    return r.text


def print_time_delta(delta, timeunits=False):
    seconds = delta.total_seconds()
    if seconds > 3600:
        if timeunits:
            return "{:02}h {:02}m {:02}s".format(int(seconds // 3600),
                                                 int((seconds % 3600) // 60),
                                                 int(seconds % 60))
        else:
            return "{:02}:{:02}:{:02}".format(int(seconds // 3600),
                                              int((seconds % 3600) // 60),
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


def list_jobs(args, printout=False):
    try:
        r = get_request(url=build_url("list/jobs"), params=args)
    except Exception as e:
        if printout:
            print(e)
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
        r = get_request(url=build_url("list/providers"))
    except Exception as e:
        if printout:
            print(e)
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
        r = get_request(url=build_url("list/instances"), params=args)
    except Exception as e:
        if printout:
            print(e)
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


def list_local_instances(printout=False):
    try:
        r = get_request(url=build_url("list/local/instances"))
    except Exception as e:
        if printout:
            print(e)
        return []
    response = r.json()["response"]
    return response


def get_full_uid(job_uid, printout=False):
    r = get_request(url=build_url("get/job_uid"), params={"job_uid": job_uid})
    full_uid = r.json().get("job_uid", None)
    if full_uid is None:
        raise MonkeyCLIJobUIDException(
            f"Unable to find the full id for shortened id: {job_uid}")
    return full_uid


def info_jobs(job_uids, printout=False):
    info = []
    for job_uid in job_uids:
        if printout:
            print(f"Retrieving info for {job_uid}")

        try:
            full_job_uid = get_full_uid(job_uid, printout)
        except MonkeyCLIException as e:
            print(f"Failed retrieving job_uid: \n{e}")
            continue

        try:
            r = get_request(url=build_url("get/job_info"),
                            params={"job_uid": full_job_uid})
        except Exception as e:
            if printout:
                print(e)
            continue
        result = r.json()
        job_info = result["job_info"]

        date_format = "%-I:%M %p %-m-%d-%y"
        # print()
        # print((job_info.keys()))
        # print(job_info)
        # print()
        # print()

        if printout:

            def print_colon_value(name, value):
                print(f"{name +':' :35} {value}")

            print_colon_value("Full monkey uid", full_job_uid)
            creation_date = datetime.datetime.utcfromtimestamp(
                job_info["creation_date"]["$date"] / 1000.0)
            print_colon_value("Created", creation_date.strftime(date_format))

            job_command = job_info["job_yml"]["cmd"]
            print_colon_value("Command run", job_command)

            job_state = human_readable_state(job_info["state"])
            print_colon_value("Job state", job_state)

            if completion_date := job_info.get("completion_date", None):
                elapsed_time = print_time_delta(
                    datetime.datetime.utcfromtimestamp(
                        completion_date["$date"] / 1000.0) - creation_date,
                    timeunits=True)
            else:
                elapsed_time = print_time_delta(datetime.datetime.now() -
                                                creation_date,
                                                timeunits=True)
            print_colon_value("Elapsed Time", elapsed_time)

            # TODO(alamp): Add more useful printout

        info.append(job_info)
    return info


def job_output(job_uid, printout=False):
    cwd = os.getcwd()
    full_uid = get_full_uid(job_uid)

    # Search for existing monkey-output directory

    def find_root_monkey_output(cwd):
        original = cwd
        root_dir_matches = ["job.yml", "monkey-output"]
        while cwd != "/":
            dir_items = os.listdir(cwd)
            for m in root_dir_matches:
                if m in dir_items:
                    return cwd
            cwd = os.path.split(cwd)[0]
        return original

    root_dir = find_root_monkey_output(cwd)
    print(f"Full uid: {full_uid}")
    output_dir = os.path.join(root_dir, "monkey-output", full_uid)
    os.makedirs(output_dir, exist_ok=True)
    if job_uid != full_uid:
        symlink_dir = os.path.join(root_dir, "monkey-output", job_uid)
        try:
            os.symlink(output_dir, symlink_dir)
        except Exception:
            pass
        output_dir = symlink_dir

    args = {"job_uid": full_uid}
    try:
        r = get_request(url=build_url("get/job/output"),
                        params=args,
                        stream=True)
    except Exception as e:
        if printout:
            print(e)
        return []

    output_tar = os.path.join(output_dir, "output.tar")

    with open(output_tar, "wb") as f:
        for chunk in r.iter_content(32 * 1024):
            f.write(chunk)

    os.chdir(output_dir)
    tf = tarfile.open(output_tar)
    tf.extractall()
    tf.close()
    os.chdir(cwd)
    print(f"\nTo see your output run:\ncd {output_dir}")
    return f"cd {output_dir}"


def info_provider(provider, printout=False):
    if printout:
        print(f"Retrieving info for {provider}")

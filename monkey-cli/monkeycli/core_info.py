import requests
from termcolor import colored

from monkeycli.utils import build_url


def get_job_uid():
    r = requests.get(build_url("get/job_uid"))
    return r.text


def list_jobs(providers, printout=False):
    r = requests.get(build_url("list/jobs"), params={"providers": providers})
    if printout:
        res = r.json()
        print("Listing Jobs available")
        for key, value in res.items():
            print("Job list for: {}".format(key))
            print("\n".join(value))
            print("Total: {}".format(len(value)))
    return r.json()


def list_providers(printout=False):
    r = requests.get(build_url("list/providers"))
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


def list_instances(providers, printout=False):
    r = requests.get(build_url("list/instances"),
                     params={"providers": providers})
    if printout:
        res = r.json()
        print("Listing Instances available\n")
        for key, value in res.items():
            print("Instance list for: {}".format(key))
            print("\n\tTotal: {}\n".format(colored(len(value), "yellow")))
            for inst in value:
                print("\tName: {} \tIP: {} \tState: {}".format(
                    colored(inst["name"], "green"), inst["ip_address"],
                    colored(inst["state"], "yellow")))
    return r.json()

#  Monkey Job Runner

### For controlling creation and deletion of cloud instances as a job runner service

#### Status
Develop Branch:
![Provider Local](https://github.com/Improbable-AI/monkey-job-runner/workflows/Provider%20Local/badge.svg?branch=actions)
![Provider AWS](https://github.com/Improbable-AI/monkey-job-runner/workflows/Provider%20AWS/badge.svg?branch=develop)
![Provider GCP](https://github.com/Improbable-AI/monkey-job-runner/workflows/Provider%20GCP/badge.svg?branch=develop)

Master Branch:
![Provider Local](https://github.com/Improbable-AI/monkey-job-runner/workflows/Provider%20Local/badge.svg?branch=master)
![Provider AWS](https://github.com/Improbable-AI/monkey-job-runner/workflows/Provider%20AWS/badge.svg?branch=master)
![Provider GCP](https://github.com/Improbable-AI/monkey-job-runner/workflows/Provider%20GCP/badge.svg?branch=master)
## Goals

1. Allow people to easily schedule, track, and manage jobs.
2. Easy to setup, use, and configure
3. Abstract away the provider in use (Google Cloud, AWS, ssh machines)
4. Allow for any sort of workflow (non-docker, script installation)
5. Allow for preemptible instances


The Monkey Job runner system is designed to augment a researchers ability to run experiments on other machines without designing any infrastructure to handle job dispatching and coordination throughout a hybrid cloud environment.  After a simple setup procedure, Monkey will handle coordination between different environments, ensuring experiments run until completion and tracking results.  Monkey is designed for researchers to use on their local machine and dispatch to other machines whenever parallelism is desired.  Monkey allows researchers to interact with the system through a couple of ways after setup is completed.

### Ad-hoc Dispatch

```bash
monkey run python3 mnist.py --learning-rate 0.14
```

### Scripting Dispatch

```python
from monkeycli import MonkeyCLI

learning_rates = ["0.01", "0.02", "0.03", "0.05", "0.10"]

for rate in learning_rates:
    monkey = MonkeyCLI()
    monkey.run("python -u mnist.py --learning-rate {}".format(rate))
```

### Hyper-parameter Sweep Dispatch

```python

from monkeycli import MonkeyCLI

learning_rates = ["0.01", "0.02", "0.03", "0.05", "0.1", "0.12"]
epochs = [ "15"]

for rate in learning_rates:
    for epoch in epochs:
        monkey = MonkeyCLI()
        monkey.run(
            "python -u mnist.py --learning-rate {} --n-epochs {}".format(
                rate, epoch))
```

## Installation

### Setting up Monkey Core
Monkey depends on *Monkey-Core* as the coordinator for all providers (**main node**).  It needs to run on a machine that will not be disconnected and can access the internet and do passwordless ssh to other local worker nodes.  It uses generally very few cpu resources but does use a lot of network bandwidth, so having *monkey-core* close to the worker nodes is generally advisable.

*Monkey-Core* is the scheduler and coordinator for the entire Monkey system.  There are multiple pieces that currently need to be run in order to use it.

First of all, go into the `*monkey-core*` directory and set up a python environment and activate it.  Currently it is tested most with `virtualenv`
```
python3 -n venv venv
source ven/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Next, *Monkey-Core* has a MongoDB running in the background to persist the metadata received.  The MongoDB is run through docker, with an included docker-compose file that makes it a one line deployment.  To start the MongoDB process and Monkey as a user of the DB run.
```
# Start with logs
docker-compose up -d

# If you would like to spawn it in the background, run.
docker-compose start

# To reattach logs run:
docker-compose logs
```

At this point *Monkey-Core* should be able to run with `./monkey_core.py`

Notes:
When *Monkey-Core* starts running, it will scan the `providers.yml` file for existing providers that it needs to setup or check.  For every cloud provider, *Monkey-Core* will mount the storage bucket as a filesystem in `ansible/monkeyfs-(aws|gcp)`.  For all local workers, *Monkey-Core* will check their availability and ensure that the worker has been set up properly.

### Monkey Core Provider Setup

For *Monkey-Core* to dispatch workloads to nodes, it needs to also set up a provider where it has permissions to do so.  There are currently only a few supported providers:
- Local
- AWS
- GCP (broken currently)
- SLURM (Future support)
- Kubernetes (Future support)

Providers are set up in *Monkey-Core* through the script `setup_core.py`, which will ask questions about the required information for setting up the provider.

To re-setup providers, you must delete the provider from the `providers.yml` file, or you can completely wipe *Monkey-Core* with the provided `./flush_all_provider_data.sh` script.

#### Local Provider Setup
A local provider functions with a couple necessary parameters.  Every worker in a local provider is treated as a machine with two necessary folder designations.  *Monkey-Core* will ask for a:
`remote filesystem mount path` - Where the main `monkeyfs` will mount to distribute data to workers efficiently
`remote scratch path` - Where scratch folders are generated temporarily to process worker requests
`monkeyfs ssh IP` - The accessible IP or hostname of *Monkey-Core* from worker nodes
`monkeyfs ssh port` - The accessible ssh port of *Monkey-Core* from worker nodes
`local.yml` - The local inventory file path, which will store information about every local node available as well as override options


#### AWS Provider Setup
TODO

Run ./setup_core

#### GCP Provider Setup
TODO

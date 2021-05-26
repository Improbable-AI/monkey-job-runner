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

First of all, go into the `*monkey_core*` directory and set up a python environment and activate it.  Currently it is tested most with `virtualenv`.  `Monkey-Core` also requires Python 3.8+
```
python3 -m venv monkey-venv
source monkey-venv/bin/activate
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

# If you get an error saying mongo-volume bind path does not exist then run
mkdir mongodb/mongo-volume
```

At this point *Monkey-Core* should run with `python3 monkey_core.py` and print out "No providers found".  Monkey-Core requires at least one provider to be set up for it to start.

Notes:
When *Monkey-Core* starts running, it will scan the `providers.yml` file for existing providers that it needs to setup or check.  For every cloud provider, *Monkey-Core* will mount the storage bucket as a filesystem in `ansible/monkeyfs-(aws|gcp)`.  For all local workers, *Monkey-Core* will check their availability and ensure that the worker has been set up properly.

### Monkey Core Provider Setup

For *Monkey-Core* to dispatch workloads to nodes, it needs to also set up a provider where it has permissions to do so.  There are currently only a few supported providers:
- AWS
- GCP
- Local (Individual Machines)
- SLURM (Future support)
- Kubernetes (Future support)

Providers are set up in *Monkey-Core* through the script `python3 setup_core.py`, which will ask questions about the required information for setting up the provider.

To re-setup providers, you must delete the provider from the `providers.yml` file, or you can completely wipe *Monkey-Core* with the provided `./flush_all_provider_data.sh` script.

To start setup, run
```
python3 setup_core.py
```
It will require a key for cloud providers, which you must provide with the correct permisions.  You must pick which providers you want to set up with `Monkey-Core` to use them as execution environments for your workflows.

#### AWS Provider Setup

##### AWS Permissions

To create an AWS Provider to dispatch runs to, you will need to create an IAM user with programmatic access and permissions to modify and automate your AWS account.  The specific permissions needed for setting up an AWS Provider is
```
AmazonEC2FullAccess
AmazonS3FullAccess
AmazonVPCFullAccess
```
These are blanket permissions that will be made more specific in the future. For now they are all needed.

After creating the programmatic IAM user, attach these permissions and then download the `.csv` key for the IAM user.  The `.csv` key should have the AWS `Access key ID` and `Secret access key`, which monkey will use to dispatch runs. Get the `.csv` file by following the instructions [here](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html#cli-configure-quickstart-creds).

##### AWS Setup

At this point you should have an AWS IAM account with programmatic access and a `.csv` key for the IAM user. 

To start setup, run `python3 setup_core.py` and choose Provider Type to be `aws`.  Then it should ask you for the `AWS Account File` which is the `.csv` that contains your AWS information.  

AWS requires `s3fs` to be installed on your local system.  
On linux install with
```
apt-get install s3fs
```
On macOS install with 
```
brew install s3fs
```

The `setup_core.py` script output will ask for other information suh as region/zone/key_name which can be overridden at this stage:
```
Create a new provider? (Y/n): 
Creating New Provider...
Provider type? (gcp, local, aws) : aws
Provider name? (aws) : 
Creating aws, type: aws
AWS Account File (should have Access key ID and Secret Access Key in csv form)
Key: personal_aws_key.csv
Set AWS region (us-east-1): 
Set AWS Zone (us-east-1a): 
Set AWS SSH Key Name (monkey_aws): 
Set the monkey_fs aws s3 bucket name (monkeyfs-rupmmz)
```

After completion of the script, Monkey will start setting up a virtual private cloud in AWS available to run instances in.  It will automaticall create and register an SSH key with AWS under `ansible/keys/`, as well as setup a subnet, internet gateway, and routing tables.  Lastly, the `setup_core.py` script will update the `providers.yml` file to include the AWS information as well as generate some files automatically to dynamically manage inventory in Ansible under `ansible/inventory/aws` and `ansible/inventory/group_vars`.  It will also create a `aws_vars.yml` file under `ansible` to provide to Ansible automation scripts.

At this point, if the `setup_core.py` automation scripts succeed, Monkey will also mount the created bucket to the host machine under `ansible/monkeyfs-aws`.  This provides a filesystem abstraction for the Monkey system to easily write files and retrieve files from the AWS provider.  Upon starting of `Monkey-Core`, if the filesystem gets demounted, it will automatically reconnect the `s3fs` mount.

To use the AWS provider on the CLI side (explained later in the doc), use `monkey init` and choose the AWS provider created in your `job.yml` creation.

#### GCP Provider Setup

##### GCP Permissions 

To create an GCP Provider to dispatch runs to, you will need to create a GCP Service Account user with programmatic access and permissions to modify and automate your GCP account. 

The specific permissions for a GCP Service Account needed for now are:

```
Editor for Compute
Admin for Storage
```
These are blanket permissions that will be made more specific in the future. For now they are all needed.

After creating the programmatic service account, attach these permissions and then download the .json key for the service account.

##### GCP Setup
At this point you should have an AWS Service Account `.json` key for the IAM user.  To start setup, run `python3 setup_core.py` and choose Provider Type to be `gcp`.  Then it should ask you for the `GVP Account File` which is the `.json` that contains your GCP information.  

GCP requires `gcsfuse` to be installed on your local system.  
On linux, this can be done with:
```
export GCSFUSE_REPO=gcsfuse-`lsb_release -c -s`
echo "deb http://packages.cloud.google.com/apt $GCSFUSE_REPO main" | sudo tee /etc/apt/sources.list.d/gcsfuse.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt-get update
sudo apt-get install gcsfuse
```

On macOS, `gcsfuse` needs to be installed via source as `brew install gcsfuse` is disabled at the time of this document:
```
brew install go osxfuse
GO111MODULE=auto go get -u github.com/googlecloudplatform/gcsfuse
```

The `setup_core.py` script output will ask for other information suh as region/zone/key_name which can be overridden at this stage:
```
Create a new provider? (Y/n): 
Creating New Provider...
Provider type? (gcp, local, aws) : gcp
Provider name? (gcp) : 
Creating gcp, type: gcp
GCP Account File (should have service account secrets in json)
Key: personal-gcp-key.json
Set GCP region (us-east1): 
Set GCP Zone (us-east1-b): 
Set GCP SSH Key Name (monkey_gcp): 
Set the monkey_fs gcp gcs bucket name (monkeyfs-aklfuc):
```

Like AWS, after completion of the script Monkey will start setting up a virtual private cloud in GCP, with subnet, internet gateway, and firewall options available to run instances in.  It will automaticall create and register an SSH key with GCP under `ansible/keys/`.  Lastly, the `setup_core.py` script will update the `providers.yml` file to include the GCP information as well as generate some files automatically to dynamically manage inventory in Ansible under `ansible/inventory/gcp` and `ansible/inventory/group_vars`.  It will also create a `gc_vars.yml` file under `ansible` to provide to Ansible automation scripts.

At this point, if the `setup_core.py` automation scripts succeed, Monkey will also mount the created bucket to the host machine under `ansible/monkeyfs-gcp`.  This provides a filesystem abstraction for the Monkey system to easily write files and retrieve files from the GCP provider.  Upon starting of `Monkey-Core`, if the filesystem gets demounted, it will automatically reconnect the `gcsfuse` mount.

To use the GCP provider on the CLI side (explained later in the doc), use `monkey init` and choose the GCP provider created in your `job.yml` creation.



#### Local Provider Setup (Beta - Individual Machines)
To set up local providers with individual machinese, it is a more involved and complicated process.  The process with more detailed explaination can be found in [local_instance_setup.md](https://github.com/Improbable-AI/monkey-job-runner/blob/develop/monkey_core/local_instance_setup.md)

#### Checking For Proper Monkey Core Setup

Quick Checklist:
* MongoDB is running in the background with `docker-compose`
* At least one provider is setup and has completed setup with `setup_core.py`

If the MongoDB is running and a provider is set up properly, then starting the `monkey_core.py` daemon should be all set.  

Upon initialization, `monkey_core.py` will run some checks on the setup providers and remount needed filesystems if needed.  After checks are completed, `Monkey-Core` will then printout job statuses every 10s.  The status will also be written to the `monkey.status` file for convenience if you would like to open a shell to `watch cat monkey.status` or `tail -f monkey.status`.  Logs for `Monkey-Core` will also be written to `monkey.log` in order to help trace bugs or understand failures in the system.

Now you should be able to run:
```
python3 monkey_core.py
```
Daemon and it should print out the status of jobs every 10-15 seconds.  
The next step then is to set up `Monkey-CLI` and your workflow.


### Setting Up Monkey CLI
The code for the `Monkey-CLI` tool is in the subfolder `monkey_cli`.  Like `Monkey-Core`, `Monkey-CLI` has its own set of dependencies.  I would recommend keeping your `Monkey-Core` installation in a different shell than the `Monkey-CLI` as the `Monkey-Core` can produce helpful logs for debugging.

To install `Monkey-CLI` in the `monkey_cli` directory create a new python environment: 
```
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Then, there are two options for setting up the Monkey-Cli.

To install it in editable mode run (Recommended)
```
pip install -e .
```
To install it in a un-editable package
```
pip install .
```
In editable mode, the *monkey-cli* live files will be used so any package does not require recompiling.  

At this point, you should be able to run the *monkey-cli* binary with `monkey`.

To expore the binary options (not all available) run:
```
> monkey --help
    run                 Run a job on the specified provider
    create              Create an instance on the specified provider
    list                List jobs on the specified provider
    info                Get info on the specified item
    output              Get the output of a job
    init                Run this command to instantiate the monkey cli with a job.yml file for your workload
```

#### Monkey-CLI Job.yml

For explaination we will use the mnist sample located under `./monkey_cli/samples/mnist`.

Before the mnist sample can be used, you will have to download the dataset with the convenience script
```
# torchvision must be installed to run it.  
pip install torchvision

# A quick way to install is to create a venv with the requirements for the sample to run it
python3 download_data.py
# This should download the mnist dataset into ./data folder
```
Lastly set up the persisted output folder:
```
mkdir output
```

Monkey-CLI requires a "job.yml" file to read in parameters to dispatch jobs to Monkey-Core.  To set up this job.yml, run the command 
```
monkey init
```
Follow the step by step instructions, and a `job.yml` file will be written to the current working directory.  Ensure that the job.yml is at the root of the workflow and all paths are relative to the `job.yml` file.


Explaination on the options chosen for the `monkey init` for this subfolder of code can be found in the [monkey_init_output.md](https://github.com/Improbable-AI/monkey-job-runner/blob/develop/monkey_cli/samples/mnist/monkey_init_output.md).

Note: Monkey works best currently on x86 based machines.  The difference between 20.04 and 18.04 Ubuntu seems to not really change things.  The Deep Learning AMI works, but often requires multiple restarts as the Deep Learning AMI is preprogrammed to pull blocking updates upon start.  The Monkey system should recover the image after a couple of restarts. 

After the `monkey init` finishes, the new `job.yml` file is written to the root of the repo to define the job.  An example `job.yml` file can be found [example_job.yml](https://github.com/Improbable-AI/monkey-job-runner/blob/develop/monkey_cli/samples/mnist/example_job.yml))


At this point, monkey is set up fully to dispatch jobs.  You can do so by using any of the listed Ad-Hoc dispatches, scripting, or sweeping approaches.  

An example of an Ad-Hoc dispatch is just prepending `monkey run` to anything you would originally run
```
monkey run python mnist.py --learning-rate 0.13
```
Examples of a sweep dispatch can be found in `param_sweep.py`.


When a run is dispatched, you should see similar following output
```
> monkey run python3 mnist.py --learning-rate 0.15 --n-epochs 2

Monkey running:
python3 mnist.py --learning-rate 0.15 --n-epochs 2

Running on provider: aws
Creating job with id:  monkey-21-05-21-1-sxj 

Uploading dataset...
Dataset checksum: 17773c10d2d974c120910922951c963b
Need to upload data...
Compressing Dataset...
/tmp/tmpb2igyj4_.tar.gz
Upload Dataset Success:  True
Uploading persisted_folder...
Persisting:  ['output']
Upload Persisted Folder: Successful

Uploading Codebase...
Codebase checksum: 54c8bf7ce4fa27c60efae8e8472c38ef
Need to upload code... codebase_found:  False
Creating codebase tar...
Upload Codebase: Successful

Submitting Job: monkey-21-05-21-1-sxj

```

From this output, we know that the unique `job_id` given to the job is `monkey-21-05-21-1-sxj`.  In order to make it easy, `job_ids` can be referred to by the last three random characters (where it will take the most recent match of the same characters), so this job can be referred to as `sxj`.

From this, we can use the `Monkey-CLI` helper tools.

To get job info pretty printed, run `monkey info job <job_id>`
```
> monkey info job sxj

Retrieving info for sxj
Full monkey uid:                    monkey-21-05-21-1-sxj
Created:                            4:32 AM 5-21-21
Command run:                        python3 mnist.py --learning-rate 0.15 --n-epochs 2
Job state:                          Installing Dependencies
Elapsed Time:                       02m 49s
```

To get a list of all monkey instances currently running, use `monkey list instances`
```
> monkey list instances

Listing Instances available

      Instance Name            Public IP            State      

Instance list for: aws, Total: 5
  monkey-21-05-21-1-xno       54.167.18.67         offline     
  monkey-21-05-21-1-xvp       3.80.52.221          running     
  monkey-21-05-21-1-sbc      54.227.121.75         running     
  monkey-21-05-21-1-sxj      34.226.205.67         running     
  monkey-21-05-21-1-aod      54.91.189.152         running
```
Note: we see the sxj instance has started running at this point.  For debugging purposes, you can ssh directly into the instance by using the `aws` provider key in `ansible/keys/`.

You can list all running jobs and there status with `monkey list jobs`
```
monkey list jobs     

Listing Jobs available

         Job Name                   Status                Created          Elapsed       Runtime   
  monkey-21-05-21-1-sxj    Installing Dependencies    05/21/21 04:32       03m 31s        0.0s   
```

To sync the job output to your local computer you can use the `monkey output <job_id>` command
```
> monkey output sxj

Full uid: monkey-21-05-21-1-sxj

To see your output run:
cd /home/avery/Developer/projects/monkey/monkey_cli/samples/mnist/monkey-output/sxj
```
The `monkey output` command will sync the persisted folders of the job into a subfolder `monkey-output`, which is created as a subdirectory under the `job.yml`.  It can be run at any time to force syncing from a provider to the local machine (to get intermediate results).


### Setup Monkey Web
The code for the `Monkey-Web` tool is in the subfolder `monkey_web`.  To install python requirements: 
```
python3 -n venv venv
source ven/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

To run the `Monkey-Web` interface, simply do
```
python index.py
```

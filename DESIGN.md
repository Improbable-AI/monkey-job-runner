# Monkey Design

## Requirements

Monkey aims to be extremely minimal in terms of requirements.  Requirements differ based on the type of providers a researcher is using.

- A **main node** machine that is always running.  Must be accessible through **https** to send jobs to.  Does not require escalated privileges.  (The **main node** can be the same machine that researchers dispatch jobs from)

### Local Provider Requirements

- A shared filesystem between **local nodes** accessible by the **main node**
- SSH access from the main node to all **local nodes**

### Cloud Provider Requirements

- **Cloud Permissions**
    - VPC permissions: creation of subnet
    - EC2 or GCE permissions: creation/deletion/edit of instances
    - S3 or GCS permissions: shared filesystem
- **main node:** Must have **s3fs** or **gcsfuse** installed to mount the provider's filesystem

## Implementation

There are a couple of parts that make up the monkey system.  
- Monkey CLI
- Monkey Framework
- Monkey Client
- Monkey Web (TODO later, visualize all jobs, create jobs, etc)

### Monkey Core

**Monkey Core** is the main coordinator of the entire monkey system.  It handles persistence of job requests, interfacing with different providers to spin up or restart instances.  **Monkey Core** coordinates tasks in multiple different ways, exposing an API (powered by [Flask](https://flask.palletsprojects.com/en/1.1.x/)) for **Monkey CLI** to submit jobs, using **[Ansible](https://www.ansible.com/)** to interface with providers and manage instances, persisting job requests in a local [MongoDB](https://www.mongodb.com/) database, and receiving and sending files to the needed shared filesystems for job dispatching.

### Monkey Core (Flask API)

The **Monkey Core** python framework contains a lightweight flask wrapper to allow a **Monkey CLI** submit a job/dataset/codebase to run and run commands to get the status of a job or instances created by **Monkey Core** in cloud providers.  The Flask API's main job is to coordinate the sending of a job from **Monkey CLI** and commit it to being run.  After receiving a job, it will commit the files to the correct filesystem to be shared with a runner node and write the metadata to the MongoDB database.  As long as the files are committed and the metadata for the run is stored in the MongoDB database, then the run will be entirely reproducible as the metadata contains all the information needed and file paths to reconstruct the run.  The Flask API coordinates the saving of packed dataset or codebase files and checksums datasets to ensure they are only uploaded once.  After the job is fully committed, the flask api will pass through the request to the Monkey Core Framework to add it to the run loop. 

### Monkey Core (Ansible)

Ansible is used to configure machines over SSH and reduce code complexity by creating Ansible Playbooks that simplify and make remote commands readable.  Ansible is also used to do cloud specific setup such as creating an AWS VPC, Subnet, Internet Gateway, and Buckets for storage.  Ansible dynamic inventories allows the Monkey Core interface to also scan cloud providers for existing instances and pull instance metadata easily.

### Monkey Core (Framework)

**Monkey Core** has a setup script that needs to be run to add providers to it and set it up on a new machine.  When running `setup.py`, it writes to various configuration files to coordinate future steps in initializing and accessing providers instances (explained in basic steps under **Installation**).  Specifically, when setting up a cloud provider, it asks for the provider credentials file and writes an Ansible Inventory file for that provider, a vars file populated with default regions/zones, filesystem bucket name and local mount point (S3, GCS), and any other information needed.  

---

### Monkey CLI

The **Monkey CLI** is the user facing program used to dispatch jobs.  It will be installable as a pypi package that helps researchers configure and setup their jobs to run.  It also is the tool that helps users make programatic sweeps across hyper-parameters.  

Monkey CLI is intended to be installed through pip as a framework that can be imported or also used directly through command line functions.  There will be a minimal command line set to start with, but eventually we hope for the cli tool to be powerful way to dispatch jobs, inspect them, track progress, and quicklink to the Monkey Website to see results or fetch them quickly. Some examples of cli function we imagine in the early stage of monkey include 

```bash
# Dispatches a job
monkey run --provider aws $CMD

# Lists current jobs
monkey list jobs --running --finished --queued
# Lists configured providers and provider based information
monkey list providers --monkey-instances
# Tails logs of the specified job
monkey logs --follow --juid 20-09-17-001

# Opens the webpage to inspect info for the job
monkey web --juid 20-09-17-001

# Modify running jobs
monkey job cancel/pause --juid 20-09-17-001
```

The Monkey CLI can also be used as an imported python framework with the code for running sweeps easily and quickly. An example of dispatching with sweeps is given above in usage examples. Likewise the imported monkey framework can also track parameters and their values over time. To do this, simply add `monkey like.log(“accuracy”, accuracy)`. The logs will be asynchronously written to a file to produce graphs of parameter values over time for viewing.  

The Monkey Cli is implemented as a stand-alone python executable that connects to the Monkey Core through the designated core api. The most important job feature is dispatching of a job. A job consists of a few major pieces (dataset, codebase, fs structure, and metadata) that needs to be sent to Monkey Core to persist and dispatch to runners available in the system. To do so, the API has multiple calls that are run in sequence to prepare and set up the job.  

---

### Monkey Client

The Monkey Client is a daemon system that is run on all worker nodes. When spinning up new instances, the Monkey Client code will be cloned and run to coordinate with Monkey Core on key events. 

The Monkey Client can help keep track of job status as well as provide logs for it current step in the running process. It will also respond to heartbeats or request a redeployment if the spot instance is marked for termination.  It is a lightweight program that Monkey Core can communicate to in order to get real-time logs and other statistics on the machine.









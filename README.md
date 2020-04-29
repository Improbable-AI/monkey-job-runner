#  Monkey Job Runner

### For controlling creation and deletion of cloud instances as a job runner service

## Goals

1. Allow people to easily schedule, track, and manage jobs.
2. Easy to setup, use, and configure
3. Abstract away the provider in use (Google Cloud, AWS, ssh machines)
4. Allow for any sort of workflow (non-docker, script installation)
5. Allow for preemptible instances

## Implementation

There are a couple of parts that make up the monkey system.  
- Monkey CLI
- Monkey Framework
- Monkey Client
- Monkey Web (TODO later, visualize all jobs, create jobs, etc)

Generally, the monkey CLI holds a Monkey Framework object, which will handle the tracking of all current jobs, dispatching of all new jobs, and other convienient features that can help interfacing with multiple providers without necessarily using their website.  The Monkey Client will be installed and run on each job-instance, and it will communicate with the Monkey Framework in order to coordinate information such as heartbeats, job status/stage, job initialization, logs, etc.

### Monkey CLI

The monkey CLI is hopefully going to be how users interact with the monkey system.  

So far there are certain commands. 
`./monkey-cli.py` Will start a monkey cmd prompt shell
executing `./monkey-cli.py arg1 arg2 ...` will execute one monkey command and return

So far the command set that I am thinking about is.
```
run
  (cmd)

# This may be removed later as run creates an instance and runs stuff
create
  instance
    - Creates an instance in the specified provider, allows for 

list
  jobs (optional: providers=[], default=all defined providers)
    - Lists all existing jobs in all providers that are running
  providers
    - Lists all defined providers (convenience)

kill
  job
    - Used to kill/cancel a job

info
  job
    - Takes in the specified job and returns info on the job status/state

```


### Monkey Framework

The monkey framework will be running as a daemon (in the future) and it should be able to restore its state (the state of all jobs, instances, etc) by just being initialized.  It highly depends on a config file, which is used to define different providers as well as machine defaults.  As in most workflows the machine defaults do not change, they will be defined in the config with overriding possible.  

Supported provider types:
- GCP
- Local (TODO)
- Slurm (TODO)
- AWS (TODO)

#### Monkey Framework Structure

The monkey framework has one main object for each provider, the `CloudHandler` object, which will have a subclass for each provider type and will manage all of the instances/jobs created in that provider.  To implement local providers, there will have to be some resource logic eventually to ensure that a machine isn't being overused.

#### Configuring the Monkey Framework 

The monkey framework is configured from a singular `providers.yml` file.  The details on configuration options can be found in `PROVDIERS.md`.


#### Running a job

Running a job on will create an instance on the specified provider, with the defined resources, and do a few things in order.

1. Create the instance
2. Pull the monkey-client script and run it (done first thing in startup-script-file).
3. Run the defined `startup-script-file` (used to configure the instance with installations)
4. Mount the specified filesystems
5. Copy the source code repo
6. Run the specified command


#### Monkey Client

The monkey client is the daemon installed on each job instance to manage a couple specific tasks.

1. The state of the job
2. Logs for the job
3. Providing debug information if things fail
4. Respond to heartbeats

In the future I can also imagine it doing things like:

5. Conditionally ending tasks (i.e. >n epoch but no results)
6. Conditionally sending job information to Slack/services
7. Storing Job stats







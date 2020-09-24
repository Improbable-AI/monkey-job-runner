# Development

### How to get set up for Monkey Development

There are a couple modules to monkey.  First, when cloned the included modules are *Monkey-Core*, *Monkey-Cli*, and Monkey-Web.  The Monkey-Client is initialized as a subrepo hosted in a public location so that all machines can pull it.  To pull subrepos:
```
git submodule update --init --recursive

```

### Monkey-Core

*Monkey-Core* is the scheduler and coordinator for the entire Monkey system.  There are multiple pieces that currently need to be run in order to use it.

First of all, go into the `*monkey-core*` directory and set up a python environment and activate it.
```
python3 -n venv venv
source ven/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Next, *Monkey-Core* has a MongoDB running in the background to persist the metadata received.  The MongoDB is run through docker, with an included docker-compose file that makes it a one line deployment.  To start the MongoDB process and Monkey as a user of the DB run.
```
# Start with logs
docker-compose up

# If you would like to spawn it in the background, run.
docker-compose start

# To reattach logs run:
docker-compose logs
```

The password encoded mongo url to manually view the database is:
```
mongodb://monkeycore:bananas@localhost:27017/monkeydb
```
I would recommend installing [MongoDB Compass](https://www.mongodb.com/try/download/compass) to view the database and objects that are stored in it.  The MongoDB compass can also be used to edit the objects which may come in handy if you need to reset a timeout without spawning more jobs.

#### Cloud providers
The last part of setting up core is to set up the specific providers that you would like to be used.  The process is automated with `./setup_core.py` for both aws and gcp support.

You will first need a iam/serviceaccount with the required Monkey Permissions to run.

#### AWS Setup
The specific permissions needed for now are:
```
AmazonEC2FullAccess
AmazonS3FullAccess
AmazonVPCFullAccess
```
These are blanket permissions that will be made more specific in the future.  For now they are all needed.

After creating the programmatic IAM user, attach these permissions and then download the `.csv` key for the IAM user.

#### GCP Setup
The specific permissions for a GCP Service Account needed for now are:
```
Editor for Compute
Admin for Storage
```
These are blanket permissions that will be made more specific in the future.  For now they are all needed.

After creating the programmatic service account, attach these permissions and then download the `.json` key for the service account.


#### Core Provider Setup
After the keys are ready, you must then setup core by running the `./setup_core.py` script to add providers and write the necessary files to run the systems.  In this process, information is extracted about the provider to create a bucket for use, configure a VPC, and setup ansible with extra information for inventory and variables needed.

`./setup_core.py` will ensure that a filesystem is created for the given provider and it will also mount the filesystem locally in `ansible/monkey-aws` or `ansible/monkey-gcp` depending on which provider is being set up.  Afterwards you can run `df -h` to ensure that the filesystem has been mounted.  `./setup_core.py` will also report whether or not the MongoDB was properly setup. 

After providers are set up, you should be ready to run `./monkey_core.py` and start *Monkey-Core* to service requests.


### Monkey-Cli

There is also setup for *Monkey-Cli* which sends jobs to *Monkey-Core*.  

To start, relocate to the `*monkey-cli*` directory and set up the python environment 

```
python3 -n venv venv
source ven/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Then, there are two options for setting up the *Monkey-Cli*.  


To install it in editable mode run (Recommended)
```
pip install -e .
```

To install it in a un-editable package 
```
pip install .
```

In editable mode, the *monkey-cli* live files will be used so any package does not require recompiling.  There is one main file in `./lib/monkeycli/monkeycli.py`

At this point, you should be able to run the *monkey-cli* binary with `monkey`.

To expore the binary options (not all available) run:
```
monkey
```

To dispatch a job, go to the samples directory `./*monkey-cli*/samples/mnist` and run with whatever options desired:
```
monkey run python mnist.py --learning-rate 0.13
```

Before the mnist sample can be used, you will have to download the dataset with the convenience script
```
# torchvision must be installed to run it.  
# A quick way to install is to create a venv with the requirements for the sample to run it
./download_data.py

```

It should connect to *Monkey Core* and give you a uid for the job in the form of:
```
monkey-yy-mm-dd-#-***
```














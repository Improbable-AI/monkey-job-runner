### Monkey Init

This is the raw output of setting up the repo with `monkey init`
Notes:
This repo has one dataset folder, under `data`
This repo has one persisted folder, under `output` (may not exist until run)
The rest of the repo is the codebase.
The repo supports `conda` and `pip` environments with the `environment.yml` and `requirements.txt` respectively

```
> monkey init


Initiating default run.yml

Project Name (monkey): 
Workflow Name (mnist): 

Please input your environment manager.
Multiple options detected...

1). Conda
2). Docker
3). Pip
4). None
Environment Type (put a number or enter your own option): 1
1
Conda selected.

Environment File (environment.yml): 


Please choose a folder for your dataset (if there is one). 
A dataset has a checksum before copying to save time on network transfer and storage.
Multiple options detected...

1). data 116.3MB
2). None/Continue
Dataset Folder(s) (put a number or enter your own option): 1
1
data 116.3MB selected.
Please choose a folder for your dataset (if there is one). 
A dataset has a checksum before copying to save time on network transfer and storage.
Selected folders: data

Dataset Folder(s) (Continue): 


Please choose any folders you would like persisted. 
Make sure your code outputs to that folder and can continue execution with the data in that folder.
Multiple options detected...

1). output
2). extra_files
3). ci
4). None/Continue
Persisted Folder(s) (put a number or enter your own option): 1
1
output selected.

Please choose any folders you would like persisted. 
Make sure your code outputs to that folder and can continue execution with the data in that folder.
Selected folders: output

Multiple options detected...

1). extra_files
2). ci
3). Continue
Persisted Folder(s) (put a number or enter your own option): 3
3
Continue selected.

Monkey Core currently has these providers available: 
(aws, type: aws)

Please choose the providers you would like to dispatch your job to.
The first provider chosen will be the default provider
Multiple options detected...

1). Name: aws, Type: aws
2). Continue
Providers (put a number or enter your own option): 1
1
Name: aws, Type: aws selected.
Do you need GPUs in your instances? [Y/n] n
Multiple options detected...

1). Compute Optimized
2). Memory Optimized
3). General
Machine Category (put a number or enter your own option): 3
3
General selected.
General category picked
Multiple options detected...

1).   2 cpus (        t3.nano |  0.5 GiB | $0.01/h)
2).   2 cpus (       t3.micro |    1 GiB | $0.01/h)
3).   2 cpus (       t3.small |    2 GiB | $0.02/h)
4).   2 cpus (      t3.medium |    4 GiB | $0.04/h)
5).   2 cpus (       t3.large |    8 GiB | $0.08/h)
6).   4 cpus (      t3.xlarge |   16 GiB | $0.17/h)
7).   8 cpus (     t3.2xlarge |   32 GiB | $0.33/h)
8). More options
Machine Type (Pick a number or enter your own machine type string): 4
4
  2 cpus (      t3.medium |    4 GiB | $0.04/h) selected.

How much space would you need in each machine (GB)?
Disk Size (10GB): 
Selected 10GB

Please pick a base image (20.04 is most supported).
Please make sure the image type is compatible with the machine type t3.medium

Your machine type t3.medium is detected to be: x86

Multiple options detected...

1). Deep Learning Ubuntu 18.04 x86 ( ami-01aad86525617098d )
2). Ubuntu 20.04 x86 ( ami-0dba2cb6798deb6d8 )
3). Ubuntu 20.04 x86 ( ami-0dba2cb6798deb6d8 )
4). Ubuntu 20.04 ARM ( ami-0ea142bd244023692 )
5). Ubuntu 18.04 x86 ( ami-0817d428a6fb68645 )
6). Ubuntu 18.04 ARM ( ami-0f2b111fdc1647918 )
Source image (Pick one or put the ami for your own custom image): 2
2
Ubuntu 20.04 x86 ( ami-0dba2cb6798deb6d8 ) selected.
Would you like your instance to be a Spot instance? [Y/n] 
Current price of a t3.medium: 0.042$/hr
Successfully added aws
Monkey Core currently has these providers available: 


Please choose the providers you would like to dispatch your job to.
Add additional providers if available
Providers (Continue): 


Renaming existing job.yml file
job.yml -> job.yml.old.1

Writing job.yml file...

```



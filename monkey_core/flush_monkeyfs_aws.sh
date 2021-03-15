#!/bin/bash

if [ -z "$1" ]
then
    echo "Pass the aws key as the second param"
    exit 1
fi

echo "Running from creds: $1"
SECRET=$(./core/setup_scripts/aws_creds_parser.py $1 -s)
KEY=$(./core/setup_scripts/aws_creds_parser.py $1 -k)
cd ansible
if [ -z "$2" ]
then
    ansible-playbook aws_cleanup_monkeyfs.yml --extra-vars "secret=$SECRET key=$KEY" -v
else

    ansible-playbook aws_cleanup_monkeyfs.yml --extra-vars "secret=$SECRET key=$KEY bucket=$2" -v
fi


#!/bin/bash

if [ -z "$1" ]
then
    echo "Pass the aws key as the second param"
    exit 1
fi

echo "Running from creds: $1"
SECRET=$(./setup_scripts/aws_creds_parser.py $1 -s)
KEY=$(./setup_scripts/aws_creds_parser.py $1 -k)
cd ansible
ansible-playbook aws_cleanup_monkeyfs.yml --extra-vars "secret=$SECRET key=$KEY" -v


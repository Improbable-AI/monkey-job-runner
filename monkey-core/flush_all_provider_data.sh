#!/bin/bash
rm providers.yml
rm local.yml
yes | rm ansible/keys/*gcp*
yes | rm ansible/keys/*aws*
rm ansible/inventory/gcp/inventory*yml
rm ansible/inventory/aws/inventory*yml
rm ansible/inventory/group_vars/*
mongo "mongodb://monkeycore:bananas@localhost:27017/monkeydb"  --eval "db.monkey_job.drop()" || echo "Dropped monkey_jobs collection successfully!"
umount ansible/monkeyfs*
rm -rf ansible/monkeyfs

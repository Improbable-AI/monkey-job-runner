#!/bin/bash
rm providers.yml
rm ansible/keys/*gcp*
rm ansible/keys/*aws*
rm ansible/inventory/gcp/inventory*yml
rm ansible/inventory/aws/inventory*yml
rm ansible/inventory/group_vars/*
rm -rf mongo/mongo-volume/*
umount ansible/monkeyfs*

#!/bin/bash
while true
do
    echo Syncing &>> ~/.sync.log
    rsync -r {{ persist_folder_path }} {{ bucket_path }} &>> ~/.sync.log
    sleep {{ persist_time | default(60, true) }}
done

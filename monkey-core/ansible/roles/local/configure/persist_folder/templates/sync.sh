#!/bin/bash
echo Syncing {{persist_folder_path}} | ts '[%m-%d %H:%M:%S]'  &>> {{sync_logs_path}}
rsync -r {{ persist_folder_path }} {{ bucket_path }} | ts '[%m-%d %H:%M:%S]'  &>> {{sync_logs_path}}

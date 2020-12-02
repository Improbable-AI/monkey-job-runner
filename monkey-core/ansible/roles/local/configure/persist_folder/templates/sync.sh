#!/bin/bash
echo Syncing {{persist_folder_path}} | ts '[%m-%d %H:%M:%S]'  &>> ~/logs/sync.log
rsync -r {{ persist_folder_path }} {{ bucket_path }} | ts '[%m-%d %H:%M:%S]'  &>> ~/logs/sync.log

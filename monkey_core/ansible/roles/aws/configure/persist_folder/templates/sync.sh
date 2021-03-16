#!/bin/bash
echo Syncing {{persist_folder_path}} | awk '{ print strftime("[%m-%d %H:%M:%S]"), $0 }'  &>> ~/logs/sync.log
rsync -r {{ persist_folder_path }} {{ bucket_path }} | awk '{ print strftime("[%m-%d %H:%M:%S]"), $0 }'  &>> ~/logs/sync.log

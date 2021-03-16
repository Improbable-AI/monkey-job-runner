#!/bin/bash
echo PERSISTING ALL | awk '{ print strftime("[%m-%d %H:%M:%S]"), $0 }'  &>> {{sync_logs_path}}
for f in {{sync_folder_path}}/*.sh; do
    f_name=$(basename $f)
    if [ $f_name != "persist_all.sh" ] && [ $f_name != {{unique_persist_all_script_name}}  ]; then
        echo "Executing sync: $f"  | awk '{ print strftime("[%m-%d %H:%M:%S]"), $0 }'  &>> {{sync_logs_path}}
        bash "$f"
    fi
done
echo PERSISTING DONE | awk '{ print strftime("[%m-%d %H:%M:%S]"), $0 }'  &>> {{sync_logs_path}}

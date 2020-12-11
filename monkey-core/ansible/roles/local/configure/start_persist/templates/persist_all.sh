#!/bin/bash
echo PERSISTING ALL | ts '[%m-%d %H:%M:%S]'  &>> {{sync_logs_path}}
for f in ~/sync/*.sh; do
    f_name=$(basename $f)
    if [ $f_name != "persist_all.sh" ] && [ $f_name != {{unique_persist_all_script_name}}  ]; then
        echo "Executing sync: $f"  | ts '[%m-%d %H:%M:%S]'  &>> {{sync_logs_path}}
        bash "$f"
    fi
done
echo PERSISTING DONE | ts '[%m-%d %H:%M:%S]'  &>> {{sync_logs_path}}

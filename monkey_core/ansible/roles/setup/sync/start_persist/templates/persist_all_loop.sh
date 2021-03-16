#!/bin/bash
while true
do
    echo Next Outer Loop, calling Persist all | awk '{ print strftime("[%m-%d %H:%M:%S]"), $0 }'  &>> {{sync_logs_path}}
    bash -c {{ persist_script_path }}
    sleep {{ persist_time | default(60 , true) }}
done

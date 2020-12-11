#!/bin/bash
while true
do
    echo Next Outer Loop, calling Persist all | ts '[%m-%d %H:%M:%S]'  &>> {{sync_logs_path}}
    bash -c {{ persist_script_path }}
    sleep {{ persist_time | default(60 , true) }}
done

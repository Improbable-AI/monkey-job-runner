#!/bin/bash
while true
do
    echo Next Outer Loop, calling Persist all |awk '{ print strftime("[%m-%d %H:%M:%S]"), $0 }'  &>> ~/logs/sync.log
    bash -c ~/sync/persist_all.sh
    sleep {{ persist_time | default(60 , true) }}
done

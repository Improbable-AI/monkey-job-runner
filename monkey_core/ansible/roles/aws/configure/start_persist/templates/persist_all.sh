#!/bin/bash
echo PERSISTING ALL | awk '{ print strftime("[%m-%d %H:%M:%S]"), $0 }'  &>> ~/logs/sync.log
for f in ~/sync/*.sh; do
    f_name=$(basename $f)
    if [ $f_name != "persist_all.sh" ] && [ $f_name != "persist_all_loop.sh" ]; then
        echo "Executing sync: $f"  | awk '{ print strftime("[%m-%d %H:%M:%S]"), $0 }'  &>> ~/logs/sync.log
        bash "$f"
    fi
done
echo PERSISTING DONE | awk '{ print strftime("[%m-%d %H:%M:%S]"), $0 }'  &>> ~/logs/sync.log

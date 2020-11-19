#!/bin/bash
echo PERSISTING ALL | ts '[%m-%d %H:%M:%S]'  &>> ~/logs/sync.log
for f in ~/sync/*.sh; do
    f_name=$(basename $f)
    if [ $f_name != "persist_all.sh" ] && [ $f_name != "persist_all_loop.sh" ]; then
        echo "Executing sync: $f"  | ts '[%m-%d %H:%M:%S]'  &>> ~/logs/sync.log
        bash "$f"
    fi
done
echo PERSISTING DONE | ts '[%m-%d %H:%M:%S]'  &>> ~/logs/sync.log

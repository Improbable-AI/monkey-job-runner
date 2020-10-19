#!/bin/bash
. ~/.monkey_activate  | tee logs/run.log
echo Activated environment correctly
echo {{ run_command }}
{{ run_command }}  2>&1 | tee logs/run.log

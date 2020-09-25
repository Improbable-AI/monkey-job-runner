#!/bin/bash
. ~/.monkey_activate  | tee logs/run.log
echo Activated environment correctly
if command -v tree > /dev/null; then
  tree
fi
echo {{ run_command }}
{{ run_command }}  2>&1 | tee logs/run.log

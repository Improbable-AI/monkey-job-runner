#!/bin/bash
. ~/.profile  | tee logs/run.log
echo Activated environment correctly
conda list
if command -v tree > /dev/null; then
  tree
fi
echo {{ run_command }}
{{ run_command }}  2>&1 | tee logs/run.log
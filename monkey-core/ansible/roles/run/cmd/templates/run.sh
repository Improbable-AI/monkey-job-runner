#!/bin/bash
. ~/.profile  | tee logs/run.log
echo Activated environment correctly
conda list
{{ run_command }}  2>&1 | tee logs/run.log
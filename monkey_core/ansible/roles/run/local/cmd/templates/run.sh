!/bin/bash
set -m
. {{activate_file}}  | tee -a {{job_dir_path}}/logs/run.log
echo Activated environment correctly 2>&1 | tee -a {{job_dir_path}}/logs/run.log
echo {{ run_command }} 2>&1 | tee -a {{job_dir_path}}/logs/run.log
{{ run_command }}  2>&1 | tee -a {{job_dir_path}}/logs/run.log

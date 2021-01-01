#!/bin/bash
. ~/.monkey_activate  | tee -a logs/run.log
echo Activated environment correctly 2>&1 | tee -a logs/run.log
echo {{ run_command }} 2>&1 | tee -a logs/run.log
{{ run_command }}  2>&1 | tee -a logs/run.log

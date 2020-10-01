#!/bin/bash
mongo "mongodb://monkeycore:bananas@localhost:27017/monkeydb"  --eval "db.monkey_job.drop()" || echo "Dropped monkey_jobs collection successfully!"

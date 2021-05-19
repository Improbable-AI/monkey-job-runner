#!/bin/bash
docker run --user mongodb --env "MONGO_INITDB_DATABASE=monkeydb" --env "MONGO_INITDB_ROOT_USERNAME=mongodb"  --env "MONGO_INITDB_DATABASE=monkeydb" --env "MONGO_INITDB_ROOT_PASSWORD=bananas" -v  "$(pwd)/mongodb/init-mongo.js:/docker-entrypoint-initdb.d/init-mongo.js:ro" -v "$(pwd)/mongodb/mongo-volume:/data/db:rw" -p 27017:27017 mongo

# Installation Instructions

## This doc is out of date, please ignore for now

### GCP

To use GCP Instances, you will need to create a service account with GCP.  To do so, go to the credentials tab under API's & Services
(Link Here)[https://console.cloud.google.com/apis/credentials]


After you download the service key, you will need to configure your project variables.  To do so, edit the file `monkey-core/providers.yml` with a name for each provider, zone, and project id.  It should align like so.

```
providers:
- name: "gcp"
  type: "gcp"
  zone: "us-east1-b"
  project: "monkey-274001"
  region: us-east1
  gcp_cred_kind: serviceaccount
  gcp_cred_file: full_path_to_key.json
```

You will also need to make sure that `monkey-core/ansible/gcp_vars.yml` and `monkey-core/ansible/inventory/gcp/inventory.compute.gcp.yml` has the correct information as well.  It will be almost a direct mirror of providers.yml, but the auto installation has not been configured yet.


## Develop Installation Instructions

To run monkey, you will need an instance of monkey-core running on your local machine which you can interface with monkey-cli to.  For now, they are run on the same machine.  They currently have one virtual environment for both of them to simplify development.

Setup venv
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements
```

Start Monkey-Core.  Runs on port 9990 for now
```
cd monkey-core
python monkey_core.py
```

Monkey core also depends on the mongodb for persistent storage.  To install and start a mongodb service for monkey usage, run `docker-compose create; docker-compose start`

To debug and view the database, use mongodb compass https://www.mongodb.com/products/compass
DB_URL = `mongodb://monkeycore:bananas@localhost:27017/monkeydb`

Interface with Monkey-CLI
```
cd monkey-cli
./monkey.py list providers
```
To change the connection or url for monkey-core
`mokney-cli/monkey.py` has the variable MONKEY_CORE_URL which has the endpoint for the monkey-core server.



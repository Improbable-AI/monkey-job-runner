# Installation Instructions


### GCP

To use GCP Instances, you will need to create a service account with GCP.  To do so, go to the credentials tab under API's & Services
(Link Here)[https://console.cloud.google.com/apis/credentials]

When a service account is created, you will need to create a key and download it to your local machine.  The service account will also need the permissions to edit compute resources
Name the key `gcp-service-key.json` and put it in the `monkey/gcp-service-key.json` folder.

After you download the service key, you will need to configure your project variables.  To do so, edit the file `monkey/cloud_providers.yaml` with a name for each provider, zone, and project id.  It should align like so.

```
providers:
    - gcp:
        type: "gcp"
        zones: 
         - "us-east1-b"
         - "us-west1-b"
        project: "gcp-project-id"
        credentials-key": "gcp-service-key.json"  # (optional), defaults

```




### Updated GCP

To use monkey with GCP you need to create a service account and create ssh keys that can be used for the os-login service

To do so

https://alex.dzyoba.com/blog/gcp-ansible-service-account/


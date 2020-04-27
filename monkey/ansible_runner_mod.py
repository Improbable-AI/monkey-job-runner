import ansible_runner

# r = ansible_runner.run(host_pattern='all', private_data_dir='ansible', cmdline="--list-hosts")

# print(r)
# for each_host_event in r.events:
#     print(each_host_event['event'])


# print(r.stats)


r = ansible_runner.run(playbook='gcp_create_job.yml', private_data_dir='ansible', inventory="ansible/inventory")

print(r)
for each_host_event in r.events:
    print(each_host_event['event'])


print(r.stats)

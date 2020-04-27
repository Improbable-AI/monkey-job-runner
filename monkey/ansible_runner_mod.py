import ansible_runner

r = ansible_runner.run(playbook='create_job.yml', private_data_dir='ansible')

print(r)
for each_host_event in r.events:
    print(each_host_event['event'])


print(r.stats)

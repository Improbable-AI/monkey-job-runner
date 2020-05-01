import ansible_runner
# import  logging 
# logging.basicConfig()
# logging.getLogger().setLevel(logging.DEBUG)
# logger = logging.getLogger(__name__)


# def ping_host(hostname):
#     r = ansible_runner.run(module='command', module_args="echo Hostname: {{inventory_hostname}}: pong", private_data_dir='ansible', host_pattern=hostname, quiet=True)
#     status, code = r.status, r.rc
#     return status == "successful" and code == 0

runner = ansible_runner.run(host_pattern="monkey-20-05-01-0", private_data_dir="ansible", module="include_role", module_args="name=install/conda", roles_path="conda")
print(runner.stats)
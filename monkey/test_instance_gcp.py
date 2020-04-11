from monkey import Monkey
from cloud.monkey_instance import MonkeyInstanceGCP
import time
m = Monkey()

gcp_cloud_provider = [p for p in m.providers if p.name == "gcp"][0]

# print(MonkeyInstanceGCP.from_ip_address(ip_address="104.196.187.20"))
print(gcp_cloud_provider.create_instance(wait_for_monkey_client=False))
print(gcp_cloud_provider.create_instance(wait_for_monkey_client=True))


# creation_operation = m.create_instance("gcp")
# print(creation_operation)

# m.wait_for_operation("gcp", creation_operation["name"])
# print(m.create())
# print(m.get_instance_list())
# print(m.get_image_list())


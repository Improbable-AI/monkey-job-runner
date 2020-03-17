from monkey import Monkey
import time
m = Monkey()

creation_operation = m.create_instance("gcp")
print(creation_operation)
m.wait_for_operation("gcp", creation_operation["name"])
# print(m.create())
# print(m.get_instance_list())
# print(m.get_image_list())


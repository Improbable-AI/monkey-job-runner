from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager
from ansible.vars.manager import VariableManager

loader = DataLoader()
inventory = InventoryManager(loader=loader, sources="ansible/inventory")
variable_manager = VariableManager(loader=loader, inventory=inventory)
print(inventory.groups)


# print(inventory)
# print(inventory.get_hosts())
# help(inventory)

# from ansible.cli.inventory import InventoryCLI

# ic = InventoryCLI(args=["monkey_gcp", "--list", "--export"])
# ic.run()
# top = ic._get_group('all')
# ic.json_inventory(inventory.groups["monkey_gcp"])
# help(ic)

# def format_group(group):
#     results = {}
#     results[group.name] = {}
#     if group.name != 'all':
#         results[group.name]['hosts'] = [h.name for h in sorted(group.hosts, key=attrgetter('name'))]
#     results[group.name]['children'] = []
#     for subgroup in sorted(group.child_groups, key=attrgetter('name')):
#         results[group.name]['children'].append(subgroup.name)
#         if subgroup.name not in seen:
#             results.update(format_group(subgroup))
#             seen.add(subgroup.name)
#     return results

a = format_group(inventory.groups["monkey_gcp"])
print(a)
for host in a["monkey_gcp"]["hosts"]:
  h = inventory.get_host(host)
  print(h.get_vars())
  # print(hosts)
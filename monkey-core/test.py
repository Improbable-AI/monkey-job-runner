# from ansible.parsing.dataloader import DataLoader
# # from ansible.vars import VariableManager
# from ansible.inventory.manager import InventoryManager
# from ansible.vars.manager import VariableManager

# loader = DataLoader()

# # loader = DataLoader()
# inventory = InventoryManager(loader=loader, sources="ansible/inventory")
# variable_manager = VariableManager(loader=loader, inventory=inventory)


# print(inventory)
# print(inventory.get_hosts())
# help(inventory)

from ansible.cli.inventory import InventoryCLI

ic = InventoryCLI(args=["monkey_gcp", "--host", "monkey_gcp"])
ic.run()
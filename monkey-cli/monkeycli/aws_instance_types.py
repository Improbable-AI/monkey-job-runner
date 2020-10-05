import os


class AWSInstanceInfo():
    def __init__(self, name, cpus, memory, storage, price, category=None):
        self.name = name
        self.cpus = cpus
        self.memory = memory
        self.storage = storage
        self.price = price
        price_str = price.split(" ")[0][1:]
        try:
            self.price_float = float(price_str)
        except:
            self.price_float = -1
        self.gpus = 0
        self.architecture = "x86"
        for sub in arm_architectures:
            if name.startswith(sub):
                self.architecture = "ARM"

    def __str__(self):
        return "Name: {}, cpus: {}, memory: {}GB, storage: {}, price: {}".format(
            self.name, self.cpus, self.memory, self.storage, self.price)


instance_type_map = {
    "gpu": ["p3", "p2"],
    "compute": ["c6", "c5"],
    "compute_minimal": ["c6."],
    "memory": ["r6g", "r5"],
    "memory_minimal": ["r6."],
    "general": ["a1", "t4g"],
    "general_minimal": ["a1."],
}

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))


def get_all_instance_types():
    with open(os.path.join(__location__, "aws_instances.txt")) as f:
        lines = f.readlines()
    instances = []
    for line in lines:
        try:
            name, cpus, ecu, memory, storage, price = line.split("\t")
            instance = AWSInstanceInfo(name, cpus, memory, storage, price)
            instances.append(instance)
        except:
            pass
    return instances


def get_instance_info(machine_type):
    instances = get_all_instance_types()
    for inst in instances:
        if inst.name == machine_type:
            return inst
    return None


def get_instance_with_type(instance_type):
    instances = get_all_instance_types()
    ret = []
    for inst in instances:
        for pretype in instance_type_map[instance_type]:
            if inst.name.startswith(pretype):
                ret.append(inst)
                break
    return ret


def aws_valid_type(machine_type):
    all_types = get_all_instance_types()
    return machine_type in [x.name for x in all_types]


arm_architectures = ["a1", "c6g", "c5a.", "t4g.", "r6g", "r5a.", "m6g", "m5a."]


def get_machine_type_architecture(machine_type):
    for sub in arm_architectures:
        if machine_type.startswith(sub):
            return "ARM"
    return "x86"


gpu_amounts = {
    "p3.2xlarge": 1,
    "p3.8xlarge": 4,
    "p3.16xlarge": 8,
    "p3dn.24xlarge": 8,
    "p2.xlarge": 1,
    "p2.8xlarge": 8,
    "p2.16xlarge": 16,
}


def get_gpu_instances():
    instances = get_instance_with_type("gpu")
    for inst in instances:
        if inst.name in gpu_amounts:
            inst.gpus = gpu_amounts[inst.name]
    return instances


def get_minimal_compute_instances():
    return get_instance_with_type("compute_minimal")


def get_compute_instances():
    return get_instance_with_type("compute")


def get_minimal_memory_instances():
    return get_instance_with_type("memory_minimal")


def get_memory_instances():
    return get_instance_with_type("memory")


def get_minimal_general_instances():
    return get_instance_with_type("general_minimal")


def get_general_instances():
    return get_instance_with_type("general")

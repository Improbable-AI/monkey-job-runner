### Local Instance Provider Setup

A local provider functions with a couple necessary parameters.  Every worker in a local provider is treated as a machine with two necessary folder designations.  *Monkey-Core* will ask for a:

`remote filesystem mount path` - Where the main `monkeyfs` will mount to distribute data to workers efficiently

`remote scratch path` - Where scratch folders are generated temporarily to process worker requests

`monkeyfs ssh IP` - The accessible IP or hostname of *Monkey-Core* from worker nodes

`monkeyfs ssh port` - The accessible ssh port of *Monkey-Core* from worker nodes

`local.yml` - The local inventory file path, which will store information about every local node available as well as override options



#!/usr/bin/env python
from monkeycli import MonkeyCLI

learning_rates = ["0.01", "0.02", "0.03", "0.05", "0.1", "0.12"]
epochs = ["3", "5"]

for rate in learning_rates:
    for epoch in epochs:
        print("\n\n----------------------------------------------\n")
        monkey = MonkeyCLI()
        monkey.run(
            "python -u mnist.py --learning-rate {} --n-epochs {}".format(
                rate, epoch))

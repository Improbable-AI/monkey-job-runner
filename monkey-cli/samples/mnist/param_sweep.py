from monkeycli.monkeycli import MonkeyCLI

learning_rates = ["0.01", "0.02", "0.03", "0.05", "0.10"]

for rate in learning_rates:
    print("\n\n----------------------------------------------\n")
    monkey = MonkeyCLI()
    monkey.run("python -u mnist.py --learning-rate {}".format(rate))

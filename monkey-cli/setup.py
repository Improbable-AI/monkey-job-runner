from setuptools import find_packages, setup

setup(
    name="monkeycli",
    version="0.0.1",
    packages=["monkeycli"],
    entry_points={'console_scripts': ['monkey=monkeycli:main']},
    install_requires=[
        "requests",  "dirhash", "pyyaml","checksumdir", "termcolor", "ruamel.yaml"
    ],
    author="Avery Lamp",
    author_email="averylamp@gmail.com",
    description="A Monkey-CLI tool used to interface with the Monkey Job runner"
)

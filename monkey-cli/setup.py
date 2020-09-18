from setuptools import setup, find_packages

setup(
    name="monkeycli",
    version="0.0.1",
    packages=["monkeycli"],
    package_dir = {"": "lib"},
    entry_points={
        'console_scripts': ['monkey=monkeycli.monkeycli:main']
    }, 
    install_requires=[
        "requests"
    ],
    author="Avery Lamp",
    author_email="averylamp@gmail.com",
    description="A Monkey-CLI tool used to interface with the Monkey Job runner"
)

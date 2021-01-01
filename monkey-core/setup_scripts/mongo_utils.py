from mongoengine import *


def get_monkey_db():
    try:
        connect("monkeydb",
                host="localhost",
                port=27017,
                username="monkeycore",
                password="bananas",
                authentication_source="monkeydb")
        return True
    except:
        print("Failure connecting to mongodb\nRun `docker-compose up`")
    return False

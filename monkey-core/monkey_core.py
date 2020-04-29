from flask import Flask, jsonify, request
application = Flask(__name__)

import os
import time
import threading

from monkey import Monkey

monkey = Monkey()

@application.route('/ping')
def ping():
    return 'pong!'

@application.route('/list/providers')
def get_list_providers():
    providers_list = monkey.get_list_providers()
    print(providers_list)
    return jsonify(providers_list)

@application.route('/list/instances')
def get_list_instances():
    print("Request")
    providers = request.args.get('providers', [])
    if len(providers) == 0:
        providers = [x["name"] for x in monkey.get_list_providers()]
    
    print("Looking up instances for providers: {}".format(providers))
    res = dict()
    for provider_name in providers:
        instances = monkey.get_list_instances(provider_name=provider_name)
        res[provider_name] = [x.get_json() for x in instances]
    
    print(res)
    return jsonify(res)

@application.route('/list/jobs')
def get_list_jobs():
    providers_list = monkey.get_list_providers()
    print(providers_list)
    return jsonify(providers_list)



@application.route('/state')
def get_state():
    return None

@application.route('/log')
@application.route('/logs')
def get_logs():
    def logs():
        with open('/var/log/monkey-client.log', 'r') as log_file:
            while True:
                yield log_file.read()
                time.sleep(1)
    return application.response_class(logs(), mimetype='text/plain')



if __name__ == '__main__':
    application.run(host='0.0.0.0', port=9990, debug=True)


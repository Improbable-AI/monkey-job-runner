#!/usr/bin/env python3.8
import argparse
import logging
import os
import sys
import time

from flask import Flask

from core import monkey_global
from core.routes.dispatch_routes import dispatch_routes
from core.routes.info_routes import info_routes

application = Flask(__name__)
application.register_blueprint(info_routes)
application.register_blueprint(dispatch_routes)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

log_format = '%(asctime)s[%(name)s]:[%(levelname)s]: %(message)s'
log_date_format = "%m-%d %H:%M:%S"
logger = logging.getLogger('core')
hdlr = logging.FileHandler(monkey_global.LOG_FILE)
formatter = logging.Formatter(log_format, log_date_format)
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)
logger = logging.getLogger('monkey')
hdlr = logging.FileHandler(monkey_global.LOG_FILE)
formatter = logging.Formatter(log_format, log_date_format)
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)
logger = logging.getLogger('mongo')
hdlr = logging.FileHandler(monkey_global.LOG_FILE)
formatter = logging.Formatter(log_format, log_date_format)
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
hdlr = logging.FileHandler(monkey_global.LOG_FILE)
formatter = logging.Formatter(log_format, log_date_format)
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)


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


def parse_args(args):
    parser = argparse.ArgumentParser(description='For extra commands')

    parser.add_argument("--dev",
                        "-d",
                        required=False,
                        default=False,
                        action="store_true",
                        dest="dev",
                        help="Auto restart core when files modified")
    parser.add_argument("--quiet",
                        "-q",
                        required=False,
                        default=None,
                        action="store_true",
                        dest="quiet",
                        help="Run quietly for all printouts")
    parser.add_argument("--ansible-quiet",
                        "-qa",
                        required=False,
                        default=None,
                        action="store_true",
                        dest="quietansible",
                        help="Run quietly for all ansible printouts")
    parser.add_argument("--periodic-quiet",
                        "-qp",
                        required=False,
                        default=None,
                        action="store_true",
                        dest="quietperiodic",
                        help="Run quietly for all periodic printouts")
    parser.add_argument("--log-file",
                        required=False,
                        default=None,
                        dest="log_file",
                        help="Run quietly for all printouts")
    parsed_args, remainder = parser.parse_known_args(args)
    if parsed_args.quiet is not None:
        monkey_global.QUIET = parsed_args.quiet
        monkey_global.QUIET_ANSIBLE = parsed_args.quiet
        monkey_global.QUIET_PERIODIC_PRINTOUT = parsed_args.quiet

    if parsed_args.quietansible is not None:
        logger.info("Running with Quiet ansible")
        monkey_global.QUIET_ANSIBLE = parsed_args.quietansible

    if parsed_args.quietperiodic is not None:
        monkey_global.QUIET_PERIODIC_PRINTOUT = parsed_args.quietperiodic
        logger.info("Running with Quiet periodic")

    if parsed_args.log_file is not None:
        monkey_global.LOG_FILE = parsed_args.log_file

    logger.info(f"Logging to { monkey_global.LOG_FILE }")
    logging.info("Starting Monkey Core logs...")
    return parsed_args


def main():
    parsed_args = parse_args(sys.argv[1:])
    if parsed_args.dev:
        logger.info("\n\nStarting in debug mode...\n\n")
        application.run(host='0.0.0.0',
                        port=9990,
                        debug=True,
                        use_reloader=True)
    else:
        application.run(host='0.0.0.0', port=9990)
    return 0


if __name__ == '__main__':
    m = monkey_global.get_monkey()
    logger.info("Starting Monkey Core")
    exit(main())

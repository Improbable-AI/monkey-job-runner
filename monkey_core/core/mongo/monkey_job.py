import json
import logging
from datetime import datetime, timedelta

from mongoengine import *

from . import mongo_global as monkey_state

logger = logging.getLogger(__name__)


class MonkeyJob(DynamicDocument):
    job_uid = StringField(required=True, unique=True)
    job_random_suffix = StringField(required=False, unique=False)
    job_yml = DictField(required=True)
    state = StringField(required=True)
    provider_type = StringField(required=True)
    provider_name = StringField(required=True)
    provider_vars = DictField(required=True, default=dict)

    # Job state
    current_ip_address = StringField(required=False)

    # Dates to store certain timing statistics
    creation_date = DateTimeField(required=True, default=datetime.now)
    last_state_change = DateTimeField(required=True, default=datetime.now)
    run_dispatch_date = DateTimeField(required=False)
    run_dispatch_machine_start_date = DateTimeField(required=False)
    run_dispatch_installs_start_date = DateTimeField(required=False)
    run_dispatch_setup_start_date = DateTimeField(required=False)
    run_running_start_date = DateTimeField(required=False)
    run_cleanup_start_date = DateTimeField(required=False)
    completion_date = DateTimeField(required=False)

    # Used to keep total run elapsed time
    run_timeout_time = IntField(required=True, default=-1)
    run_elapsed_time = IntField(required=True, default=0)
    total_wall_time = IntField(required=True, default=0)

    # Experiment config, hyperparameters
    experiment_hyperparameters = DictField(required=False, default=dict)

    meta = {
        'indexes': [
            'job_uid',  # text index for uid
            '$state',  # text index for state
        ]
    }

    def get_dict(self):
        return json.loads(self.to_json())

    def set_state(self, state):
        """ Sets the state and updates needed timestamps

        Args:
            state (MONKEY_STATE): The state to update to
        """
        logger.info("Setting job: {} state to: {}, from: {}".format(
            self.job_uid, state, self.state))

        if (self.state == monkey_state.MONKEY_STATE_RUNNING) and (
                state != monkey_state.MONKEY_STATE_RUNNING):
            self.run_elapsed_time += self.time_elapsed_in_state()

        self.state = state
        if state == monkey_state.MONKEY_STATE_DISPATCHING_MACHINE:
            self.run_dispatch_machine_start_date = datetime.now()
        elif state == monkey_state.MONKEY_STATE_DISPATCHING_INSTALLS:
            self.run_dispatch_installs_start_date = datetime.now()
        elif state == monkey_state.MONKEY_STATE_DISPATCHING_SETUP:
            self.run_dispatch_setup_start_date = datetime.now()
        elif state == monkey_state.MONKEY_STATE_RUNNING:
            self.run_running_start_date = datetime.now()
        elif state == monkey_state.MONKEY_STATE_CLEANUP:
            self.run_cleanup_start_date = datetime.now()
        elif state == monkey_state.MONKEY_STATE_FINISHED:
            self.completion_date = datetime.now()
            self.total_wall_time = (datetime.now() - self.creation_date).total_seconds()
        self.last_state_change = datetime.now()
        self.save()

    def time_elapsed_in_state(self):
        return (datetime.now() - self.last_state_change).total_seconds()

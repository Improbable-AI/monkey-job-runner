from mongoengine import *
from datetime import datetime, timedelta
MONKEY_STATE_QUEUED = "QUEUED"
MONKEY_STATE_DISPATCHING = "DISPATCHING"
MONKEY_STATE_DISPATCHING_MACHINE = "DISPATCHING_MACHINE"
MONKEY_STATE_DISPATCHING_INSTALLS = "DISPATCHING_INSTALLS"
MONKEY_STATE_DISPATCHING_SETUP = "DISPATCHING_SETUP"
MONKEY_STATE_RUNNING = "RUNNING"
MONKEY_STATE_CLEANUP = "CLEANING_UP"
MONKEY_STATE_FINISHED = "FINISHED"


MONKEY_TIMEOUT_DISPATCHING_MACHINE = 60 * 3 # 5 min to dispatch machine max
MONKEY_TIMEOUT_CLEANUP = 60 * 5 # 5 min to dispatch machine max

class MonkeyJob(DynamicDocument):
    job_uid = StringField(required=True, unique=True)
    job_yml = DictField(required=True)
    state = StringField(required=True)
    provider_type = StringField(required=True)
    provider_name = StringField(required=True)
    provider_vars = DictField(required=True, default=dict)

    # Dates to store certain timing statistics
    creation_date = DateTimeField(required=True, default=datetime.now)
    run_dispatch_date = DateTimeField(required=False)
    run_dispatch_machine_start_date = DateTimeField(required=False)
    run_dispatch_installs_start_date = DateTimeField(required=False)
    run_dispatch_setup_start_date = DateTimeField(required=False)
    run_runing_start_date = DateTimeField(required=False)
    run_cleanup_start_date = DateTimeField(required=False)
    completion_date = DateTimeField(required=False)


    # Used to keep total run elapsed time
    run_timeout_time = IntField(required=True, default=-1)
    run_elapsed_time = IntField(required=True, default=0)


    meta = {
        'indexes': [
            'job_uid',  # text index for uid
            '$state',  # text index for state
        ]
    }

    def set_state(self, state):
        """ Sets the state and updates needed timestamps

        Args:
            state (MONKEY_STATE): The state to update to
        """
        print("Setting job: {} state to: {}, from: {}".format(self.job_uid, state, self.state))
        self.state = state
        if state == MONKEY_STATE_DISPATCHING_MACHINE:
            self.run_dispatch_machine_start_date = datetime.now()
        elif state == MONKEY_STATE_DISPATCHING_INSTALLS:
            self.run_dispatch_installs_start_date = datetime.now()
        elif state == MONKEY_STATE_DISPATCHING_SETUP:
            self.run_dispatch_setup_start_date = datetime.now()
        elif state == MONKEY_STATE_RUNNING:
            self.run_running_start_date = datetime.now()
        elif state == MONKEY_STATE_CLEANUP:
            self.run_cleanup_start_date = datetime.now()
        elif state == MONKEY_STATE_FINISHED:
            self.completion_date = datetime.now()
            if self.run_cleanup_start_date is None:
                # Ensures cleanup will be run immediately
                self.run_cleanup_start_date = datetime.now() - timedelta(days=5)
        self.save()
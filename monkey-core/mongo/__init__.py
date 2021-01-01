from mongo.mongo_global import (MONKEY_STATE_CLEANUP, MONKEY_STATE_DISPATCHING,
                                MONKEY_STATE_DISPATCHING_INSTALLS,
                                MONKEY_STATE_DISPATCHING_MACHINE,
                                MONKEY_STATE_DISPATCHING_SETUP,
                                MONKEY_STATE_FINISHED, MONKEY_STATE_QUEUED,
                                MONKEY_STATE_RUNNING, MONKEY_TIMEOUT_CLEANUP,
                                MONKEY_TIMEOUT_DISPATCHING_INSTALLS,
                                MONKEY_TIMEOUT_DISPATCHING_MACHINE,
                                MONKEY_TIMEOUT_DISPATCHING_SETUP,
                                state_to_timeout)
from mongo.mongo_utils import get_monkey_db
from mongo.monkey_job import MonkeyJob

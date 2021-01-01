MONKEY_STATE_QUEUED = "QUEUED"
MONKEY_STATE_DISPATCHING = "DISPATCHING"
MONKEY_STATE_DISPATCHING_MACHINE = "DISPATCHING_MACHINE"
MONKEY_STATE_DISPATCHING_INSTALLS = "DISPATCHING_INSTALLS"
MONKEY_STATE_DISPATCHING_SETUP = "DISPATCHING_SETUP"
MONKEY_STATE_RUNNING = "RUNNING"
MONKEY_STATE_CLEANUP = "CLEANING_UP"
MONKEY_STATE_FINISHED = "FINISHED"

MONKEY_TIMEOUT_DISPATCHING_MACHINE = 60 * 4  # 4 min to dispatch machine max
MONKEY_TIMEOUT_DISPATCHING_INSTALLS = 60 * 10  # 10 min to dispatch installs max
MONKEY_TIMEOUT_DISPATCHING_SETUP = 60 * 3  # 3 min to dispatch setup max
MONKEY_TIMEOUT_CLEANUP = 30  # 30s to dispatch machine max


def human_readable_state(state):
    if state == MONKEY_STATE_QUEUED:
        return "Queued"
    elif state == MONKEY_STATE_DISPATCHING:
        return "Dispatching Machine"
    elif state == MONKEY_STATE_DISPATCHING_MACHINE:
        return "Dispatching Machine"
    elif state == MONKEY_STATE_DISPATCHING_INSTALLS:
        return "Installing Dependencies"
    elif state == MONKEY_STATE_DISPATCHING_SETUP:
        return "Setting up Job"
    elif state == MONKEY_STATE_RUNNING:
        return "Running"
    elif state == MONKEY_STATE_CLEANUP:
        return "Cleaning Up"
    elif state == MONKEY_STATE_FINISHED:
        return "Finished"
    else:
        return state


def state_to_timeout(state):
    if state == MONKEY_STATE_DISPATCHING:
        return MONKEY_TIMEOUT_DISPATCHING_MACHINE
    if state == MONKEY_STATE_DISPATCHING_MACHINE:
        return MONKEY_TIMEOUT_DISPATCHING_MACHINE
    if state == MONKEY_STATE_DISPATCHING_INSTALLS:
        return MONKEY_TIMEOUT_DISPATCHING_INSTALLS
    if state == MONKEY_STATE_DISPATCHING_SETUP:
        return MONKEY_TIMEOUT_DISPATCHING_SETUP
    if state == MONKEY_STATE_CLEANUP:
        return MONKEY_TIMEOUT_CLEANUP
    return None

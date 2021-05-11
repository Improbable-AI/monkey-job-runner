import dash
import requests

from datetime import datetime
import timeago

DATA_REFRESH_INTERVAL = 60000 # milliseconds

MONKEY_CORE = 'http://localhost:9990'
MONKEY_STATUS = {
        'QUEUED': 'Queued',
        'DISPATCHING': 'Dispatching',
        'DISPATCHING_MACHINE': 'Dispatching',
        'DISPATCHING_INSTALLS': 'Dispatching',
        'DISPATCHING_SETUP': 'Dispatching',
        'RUNNING': 'Running',
        'CLEANING_UP': 'Running',
        'FINISHED': 'Finished',
        }

external_stylesheets = ['https://cdn.jsdelivr.net/npm/bootstrap@5.0.0-beta3/dist/css/bootstrap.min.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server


def get_run_list(project=None):
    try:
        r = requests.get(f'{MONKEY_CORE}/list/jobs')
        r.raise_for_status()
        response = r.json()
    except:
        raise
    runs = [{
        'id': run.get('job_uid', 'no-run-id'),
        'name': run['job_yml'].get('name', 'Unnamed run'),
        'project': run['job_yml'].get('project_name', 'Unnamed project'),
        'status': MONKEY_STATUS.get(run['state'], 'Unknown'),
        'deployed': timeago.format(
            datetime.utcfromtimestamp(run['creation_date']['$date'] / 1000),
            datetime.now()).capitalize(),
        'hyperparameters': run['experiment_hyperparameters'],
        } for run in response]
    return [run for run in runs
            if project is None or run['project'] == project]

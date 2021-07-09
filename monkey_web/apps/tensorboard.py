import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State

import json
import requests
from tensorboard import program
import threading

from app import app, MONKEY_CORE, MONKEY_STATUS, get_run_list


tensorboard_registry = {}
lock = threading.Lock()

class TensorboardViewer:
    def __init__(self, project_id, run_id, logdir, interval=3600.0):
        self.project_id = project_id
        self.run_id = run_id
        tb = program.TensorBoard()
        tb.configure(argv=[None, '--logdir', logdir])
        self.server = tb._make_server()
        self.thread = threading.Thread(target=self.server.serve_forever, name="TensorBoard")
        self.thread.daemon = True
        self.manager = threading.Timer(interval, self.shutdown)
        self.manager.daemon = True

    def launch(self):
        self.thread.start()
        self.manager.start()
        self.url = self.server.get_url()
        tensorboard_registry[self.project_id, self.run_id] = self

    def shutdown(self):
        with lock:
            del tensorboard_registry[self.project_id, self.run_id]
        self.server.shutdown()


def get_layout(project_id, run_id):
    return html.Div(children=[
        dcc.Store(id='tensorboard-current-project', data=project_id),
        dcc.Store(id='tensorboard-current-run', data=run_id),

        html.Div(className='container', children=[
            html.H1(children=[
                html.Span('Viewing Tensorboard '),
                html.Span(f'for project {project_id}: {run_id}', className='small'),
                ]),
                html.Iframe(className='w-100 vh-100',
                    src=get_tensorboard_link(project_id, run_id),
                    ),
            ]),
        ])


def get_run_monkeyfs_path(project_id, run_id):
    try:
        r = requests.get(f'{MONKEY_CORE}/get/job_info', params={'job_uid': run_id})
        r.raise_for_status()
        return r.json()['job_info']['provider_vars']['local_monkeyfs_path']
    except:
        raise

def get_tensorboard_link(project_id, run_id):
    print('Generating tensorboard link')
    with lock:
        if (project_id, run_id) in tensorboard_registry:
            print('Returning pre-existing link')
            return tensorboard_registry[project_id, run_id].url
        print('Creating tensorboard object')
        logdir = get_run_monkeyfs_path(project_id, run_id)
        viewer = TensorboardViewer(project_id, run_id, logdir=logdir)
        print('Launching tensorboard')
        viewer.launch()
    print('Returning link', viewer.url)
    return viewer.url

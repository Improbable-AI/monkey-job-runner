import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State

import json
import requests

from app import app, MONKEY_CORE, MONKEY_STATUS, get_run_list


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


def get_tensorboard_link(project_id, run_id):
    return 'http://localhost:6006'

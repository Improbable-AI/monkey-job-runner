import dash_core_components as dcc
import dash_html_components as html
import dash_table
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from datetime import datetime
import json
import requests
import timeago

from app import app, MONKEY_CORE, MONKEY_STATUS, get_run_list


HYPERPARAMETER_PREFIX = 'hyp-'

RUN_TABLE_BASE_COLUMNS = [
        {'name': '#', 'id': 'id', 'type': 'text', 'hideable': True},
        {'name': 'Run name', 'id': 'name', 'type': 'text', 'hideable': True},
        {'name': 'Status', 'id': 'status', 'type': 'text', 'hideable': True},
        {'name': 'Deployed', 'id': 'deployed', 'type': 'text', 'hideable': True},
        ]

RUN_TABLE_OPTIONS = {
        'filter_action': 'native',
        'row_selectable': 'single', # TODO[jerry]: replace with multi to support comparisons
        'sort_action': 'native',
        'sort_mode': 'multi',
        'style_cell': {
            'font-family': 'sans-serif',
            'padding': '5px',
            'text-align': 'left',
            },
        'style_data': {
            'cursor': 'pointer',
            },
        'style_filter': {
            'text-align': 'left',
            },
        'style_header': {'font-weight': 'bold'},
        'style_table': {'overflow': 'auto'},
        }


def get_layout(project_id, run_id=None):
    runs = to_hyperparameter_list(get_run_list(project=project_id))
    columns = get_column_spec(runs)
    run_info = html.P('Select a run to view details') if run_id is None else get_run_info(run_id)

    return html.Div(children=[
        dcc.Store(id='project-current-project', data=project_id),
        dcc.Store(id='project-current-run', data=run_id),
        dcc.Store(id='project-run-list', data=runs),

        html.Div(className='row', children=[
            html.Div(className='col-12 col-md-4 offset-md-8 p-3 border-left border-bottom', children=[
                html.H5(className='mb-0', children=f'Project: {project_id}'),
                ]),
            ]),
        html.Div(className='row', children=[
            html.Div(className='col-12 col-md-8 pr-0', children=[
                dash_table.DataTable(
                    id='project-run-table',
                    columns=columns,
                    data=runs,
                    selected_rows=[i for i, run in enumerate(runs) if run['id'] == run_id],
                    **RUN_TABLE_OPTIONS
                    ),
                ]),

            html.Div(className='col-12 col-md-4 p-3 border-left border-bottom', children=[
                run_info
                ]),
            ]),
        ])


def get_run_info(run_id):
    try:
        r = requests.get(f'{MONKEY_CORE}/get/job_info', params={'job_uid': run_id})
        r.raise_for_status()
        response = r.json()['job_info']
    except:
        raise
    return html.Div(children=[
            html.Dt('Monkey id'), html.Dd(run_id),
            html.Dt('Run name'), html.Dd(response['job_yml'].get('name', 'Unnamed workflow')),
            html.Dt('Run status'), html.Dd(MONKEY_STATUS[response['state']]),
            ])


def to_hyperparameter_list(raw_runs):
    return [dict(
        id=run['id'],
        name=run['name'],
        status=run['status'],
        deployed=run['deployed'],
        **{f'{HYPERPARAMETER_PREFIX}{key}': run['hyperparameters'][key]
            for key in run['hyperparameters']}
        ) for run in raw_runs]


def get_column_spec(runs):
    hyperparameters = set(key
            for run in runs
            for key in run
            if key.startswith(HYPERPARAMETER_PREFIX))
    return RUN_TABLE_BASE_COLUMNS + [
            {'name': key[len(HYPERPARAMETER_PREFIX):], 'id': key, 'hideable': True}
            for key in sorted(list(hyperparameters))
            ]

@app.callback(Output('app-url', 'pathname'),
              Input('project-run-table', 'selected_rows'),
              State('project-run-list', 'data'),
              State('app-path', 'data'))
def update_selected_run(selected_runs, runs, path):
    if path[:1] != ['project']:
        raise PreventUpdate
    result = None
    assert len(selected_runs) <= 1
    if selected_runs == []:
        result = path[:2]
    else:
        result = path[:2] + [runs[selected_runs[0]]['id']]
    if result == path:
        raise PreventUpdate
    return '/'.join([''] + result)

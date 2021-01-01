import dash_core_components as dcc
import dash_html_components as html
import dash_table
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from app import app, MONKEY_CORE, MONKEY_STATUS, get_run_list


DASHBOARD_RUNS_COLUMNS = [
        {'name': '#', 'id': 'id', 'type': 'text'},
        {'name': 'Run name', 'id': 'name', 'type': 'text'},
        {'name': 'Project', 'id': 'project', 'type': 'text'},
        {'name': 'Status', 'id': 'status', 'type': 'text'},
        {'name': 'Deployed', 'id': 'deployed', 'type': 'text'},
        ]

DASHBOARD_TABLE_OPTIONS = {
        'filter_action': 'native',
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
        }


def get_layout():
    runs = get_run_list()
    return html.Div(className='container my-5', children=[
        dcc.Store(id='dashboard-run-list', data=runs),

        html.H1(children='Dashboard'),

        html.Div(className='mb-4', children=[
            html.H2(children='Recent projects'),
            html.Ul(children=[
                html.Li(children=[
                    dcc.Link(href=f'/project/{project["id"]}', children=project['id']),
                    html.Span(f' ({project["n_runs"]} runs)')
                    ])
                for project in to_project_list(runs)
                ]),
            ]),

        html.Div(className='mb-4', children=[
            html.H2(children='Recent runs'),
            dash_table.DataTable(
                id='dashboard-run-table',
                columns=DASHBOARD_RUNS_COLUMNS,
                data=runs,
                **DASHBOARD_TABLE_OPTIONS
                ),
            ]),
        ])


def to_project_list(runs):
    projects = {}
    for run in runs:
        project = projects.setdefault(run['project'], {'n_runs': 0})
        project['n_runs'] += 1
    return [
            dict(id=project, project=project, **projects[project])
            for project in projects]


@app.callback(Output('dashboard-run-list', 'data'),
              Input('app-interval', 'n_intervals'),
              State('app-path', 'data'))
def update_run_list(_, path):
    if path[:1] != ['']:
        raise PreventUpdate
    return get_run_list()


@app.callback(Output('dashboard-run-table', 'data'),
              Input('dashboard-run-list', 'data'),
              State('app-path', 'data'))
def update_run_table(runs, path):
    if path[:1] != ['']:
        raise PreventUpdate
    return runs


"""
# Dash struggles with multiple datatable callbacks
@app.callback(Output('app-url', 'pathname'),
              Input('dashboard-run-table', 'active_cell'),
              State('app-path', 'data'))
def onclick_run(active_run, path):
    if path[:1] != ['']:
        raise PreventUpdate
    if active_run is not None:
        run_id = active_run['row_id']
        return f'/run/{run_id}'
    raise PreventUpdate
"""

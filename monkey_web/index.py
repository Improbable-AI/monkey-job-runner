#!/usr/bin/env python

import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate

from app import app, DATA_REFRESH_INTERVAL
from apps import dashboard, project, tensorboard

app.layout = html.Div(children=[
    dcc.Location(id='app-url', refresh=False),
    dcc.Store(id='app-path', data=['']),

    dcc.Interval(
        id='app-interval',
        interval=DATA_REFRESH_INTERVAL,
        ),

    html.Nav(className='navbar navbar-dark bg-dark mb-5', children=[
        html.Div(className='container', children=[
            dcc.Link(className='navbar-brand', href='/',
                children='Experiment visualizer'),
                ]),
        ]),

    html.Div(id='app-content'),
    ])


@app.callback(Output('app-path', 'data'),
              Input('app-url', 'pathname'))
def parse_path(pathname):
    if pathname is None:
        return ['']
    return pathname.lstrip('/').split('/')


@app.callback(Output('app-content', 'children'),
              Input('app-path', 'data'))
def display_page(path):
    if path == ['']:
        return dashboard.get_layout()
    elif path[0] == 'project':
        if len(path) == 1:
            return '404'
        elif len(path) == 2:
            return project.get_layout(path[1])
        else:
            return project.get_layout(path[1], path[2])
    elif path[0] == 'run':
        return compare.get_layout(pathname[5:])
    elif path[0] == 'tensorboard':
        if len(path) != 3:
            return '404'
        return tensorboard.get_layout(path[1], path[2])
    else:
        return '404'

if __name__ == '__main__':
    app.run_server(debug=True)

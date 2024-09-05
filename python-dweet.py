import json
import time
import threading
import pandas as pd
import paho.mqtt.client as mqtt
import dash
from dash import dcc, html
import plotly.graph_objs as go
from dash.dependencies import Input, Output, State
import ast

# Load configuration
config_path = "config.json"
with open(config_path, 'r') as f:
    config = json.load(f)

# MQTT Client Setup
client = mqtt.Client()

# Global variables
latest_data = {}
publish_flag = False
publish_thread = None

# Dash App Setup
app = dash.Dash(__name__, suppress_callback_exceptions=True)

app.layout = html.Div([
    html.H1("MQTT Dashboard", style={'textAlign': 'center', 'padding': '20px 0', 'color': '#333'}),
    
    # Custom Toggle Switch for Demo Data
    html.Div([
        html.Label("Read Demo Data", style={'fontSize': '20px', 'marginRight': '10px'}),
        dcc.Checklist(
            id='read-demo-data-toggle',
            options=[{'label': '', 'value': 'read_demo'}],
            value=['read_demo'] if config['read_demo_data'] else [],
            style={'display': 'inline-block', 'margin': '0'},
            inputStyle={"margin-right": "10px", "transform": "scale(1.5)"},
            labelStyle={'display': 'inline-block'}
        )
    ], style={'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center', 'marginBottom': '20px'}),

    html.Div(id='demo-controls', style={'textAlign': 'center', 'marginBottom': '20px'}),
    
    # Graphs Container
    html.Div(id='graphs', style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'center'}),
    
    dcc.Interval(id='interval-component', interval=2000, n_intervals=0),
    dcc.Store(id='gauge-settings', data={}),
    dcc.Store(id='input-values', data={}),
], style={'fontFamily': 'Arial, sans-serif', 'backgroundColor': '#f4f4f4', 'padding': '20px'})


def create_gauge_figure(value, title, min_val=0, max_val=100, color="darkblue"):
    if not color:
        color = "darkblue"

    return go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={'text': title},
            gauge={
                'axis': {'range': [min_val, max_val]},
                'bar': {'color': color},
                'steps': [
                    {'range': [min_val, (max_val-min_val)*0.5 + min_val], 'color': "lightgray"},
                    {'range': [(max_val-min_val)*0.5 + min_val, max_val], 'color': "gray"}
                ]
            }
        )
    )

@app.callback(
    Output('input-values', 'data'),
    Input({'type': 'title-input', 'index': dash.dependencies.ALL}, 'value'),
    Input({'type': 'min-value-input', 'index': dash.dependencies.ALL}, 'value'),
    Input({'type': 'max-value-input', 'index': dash.dependencies.ALL}, 'value'),
    Input({'type': 'color-input', 'index': dash.dependencies.ALL}, 'value'),
    Input({'type': 'graph-type-dropdown', 'index': dash.dependencies.ALL}, 'value'),
    State('input-values', 'data')
)
def store_input_values(titles, min_values, max_values, colors, graph_types, current_values):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update

    for i, component_id in enumerate(ctx.inputs):
        json_part = component_id.split('.')[0]
        gauge_index = ast.literal_eval(json_part)['index']

        title = titles[i] if i < len(titles) else None
        min_val = min_values[i] if i < len(min_values) else None
        max_val = max_values[i] if i < len(max_values) else None
        color = colors[i] if i < len(colors) else None
        graph_type = graph_types[i] if i < len(graph_types) else None

        if title is not None and min_val is not None and max_val is not None and color is not None and graph_type is not None:
            current_values[gauge_index] = {
                'title': title,
                'min_val': min_val,
                'max_val': max_val,
                'color': color,
                'graph_type': graph_type
            }

    return current_values

    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update

    for i, component_id in enumerate(ctx.inputs):
        json_part = component_id.split('.')[0]
        gauge_index = ast.literal_eval(json_part)['index']

        title = titles[i] if i < len(titles) else None
        min_val = min_values[i] if i < len(min_values) else None
        max_val = max_values[i] if i < len(max_values) else None
        color = colors[i] if i < len(colors) else None

        if title is not None and min_val is not None and max_val is not None and color is not None:
            current_values[gauge_index] = {
                'title': title,
                'min_val': min_val,
                'max_val': max_val,
                'color': color
            }

    return current_values

@app.callback(
    Output('gauge-settings', 'data'),
    Input({'type': 'save-btn', 'index': dash.dependencies.ALL}, 'n_clicks'),
    State('input-values', 'data'),
    State('gauge-settings', 'data')
)
def save_gauge_settings(n_clicks, input_values, current_settings):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    gauge_index = json.loads(button_id)['index']

    if gauge_index in input_values:
        current_settings[gauge_index] = {
            'title': input_values[gauge_index]['title'],
            'min_val': float(input_values[gauge_index]['min_val']),
            'max_val': float(input_values[gauge_index]['max_val']),
            'color': input_values[gauge_index]['color']
        }
        
        for gauge in config['dashboard_gauges']:
            if gauge['value_key'] == gauge_index:
                gauge.update(current_settings[gauge_index])

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)

    return current_settings

def create_graph(value, title, graph_type, min_val=0, max_val=100, color="darkblue"):
    # Ensure the color is valid
    if not color or len(color) < 3:  # Check if the color is too short to be valid
        color = "darkblue"  # Default to dark blue if the color is invalid
    
    if graph_type == 'Gauge':
        return go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=value,
                title={'text': title},
                gauge={
                    'axis': {'range': [min_val, max_val]},
                    'bar': {'color': color},
                    'steps': [
                        {'range': [min_val, (max_val-min_val)*0.5 + min_val], 'color': "lightgray"},
                        {'range': [(max_val-min_val)*0.5 + min_val, max_val], 'color': "gray"}
                    ]
                }
            )
        )
    elif graph_type == 'Line':
        return go.Figure(
            go.Scatter(
                y=[value],
                mode='lines',
                line=dict(color=color),  # Valid color string is passed here
                name=title
            )
        )
    elif graph_type == 'Bar':
        return go.Figure(
            go.Bar(
                y=[value],
                marker=dict(color=color),  # Valid color string is passed here
                name=title
            )
        )
    # Add more graph types if needed
    return go.Figure()  # Default empty figure
    if graph_type == 'Gauge':
        return go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=value,
                title={'text': title},
                gauge={
                    'axis': {'range': [min_val, max_val]},
                    'bar': {'color': color},
                    'steps': [
                        {'range': [min_val, (max_val-min_val)*0.5 + min_val], 'color': "lightgray"},
                        {'range': [(max_val-min_val)*0.5 + min_val, max_val], 'color': "gray"}
                    ]
                }
            )
        )
    elif graph_type == 'Line':
        return go.Figure(
            go.Scatter(
                y=[value],
                mode='lines',
                line=dict(color=color),
                name=title
            )
        )
    elif graph_type == 'Bar':
        return go.Figure(
            go.Bar(
                y=[value],
                marker=dict(color=color),
                name=title
            )
        )
    # Add more graph types if needed
    return go.Figure()  # Default empty figure

def update_dashboard(gauge_settings, input_values):
    graphs = []
    for gauge in config['dashboard_gauges']:
        value_key = gauge['value_key']
        value = latest_data.get(value_key, 0)
        
        settings = gauge_settings.get(value_key, {})
        title = input_values.get(value_key, {}).get('title', gauge['title'])
        min_val = input_values.get(value_key, {}).get('min_val', gauge.get('min_val', 0))
        max_val = input_values.get(value_key, {}).get('max_val', gauge.get('max_val', 100))
        color = input_values.get(value_key, {}).get('color', gauge.get('color', 'darkblue'))
        graph_type = input_values.get(value_key, {}).get('graph_type', 'Gauge')  # Default to 'Gauge'

        graph = html.Div([
            html.Div([
                dcc.Input(id={'type': 'title-input', 'index': value_key}, type='text', value=title, placeholder='Title', style={'marginRight': '10px', 'marginBottom': '5px'}),
                dcc.Input(id={'type': 'min-value-input', 'index': value_key}, type='number', value=min_val, placeholder='Min Value', style={'marginRight': '10px', 'marginBottom': '5px'}),
                dcc.Input(id={'type': 'max-value-input', 'index': value_key}, type='number', value=max_val, placeholder='Max Value', style={'marginRight': '10px', 'marginBottom': '5px'}),
                dcc.Input(id={'type': 'color-input', 'index': value_key}, type='text', value=color, placeholder='Bar Color', style={'marginRight': '10px', 'marginBottom': '5px'}),
                dcc.Dropdown(
                    id={'type': 'graph-type-dropdown', 'index': value_key},
                    options=[
                        {'label': 'Gauge', 'value': 'Gauge'},
                        {'label': 'Line', 'value': 'Line'},
                        {'label': 'Bar', 'value': 'Bar'},
                        # Add more graph types if needed
                    ],
                    value=graph_type,
                    style={'width': '120px', 'marginRight': '10px', 'marginBottom': '5px'}
                ),
                html.Button('Save', id={'type': 'save-btn', 'index': value_key}, n_clicks=0, style={'padding': '5px 10px', 'backgroundColor': '#007bff', 'color': 'white', 'border': 'none', 'borderRadius': '5px'})
            ], style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'center', 'alignItems': 'center', 'marginBottom': '10px'}),
            dcc.Graph(
                id={'type': 'dynamic-graph', 'index': value_key},
                figure=create_graph(value, title, graph_type, min_val=min_val, max_val=max_val, color=color)
            ),
        ], style={'width': '100%', 'maxWidth': '400px', 'padding': '20px', 'margin': '10px', 'backgroundColor': 'white', 'boxShadow': '0 2px 4px rgba(0, 0, 0, 0.1)', 'borderRadius': '10px'})
        graphs.append(graph)
    return graphs


@app.callback(
    Output('graphs', 'children'),
    Input('interval-component', 'n_intervals'),
    Input('gauge-settings', 'data'),
    State('input-values', 'data')
)
def refresh_graphs(n_intervals, gauge_settings, input_values):
    return update_dashboard(gauge_settings, input_values)

def on_message(client, userdata, msg):
    global latest_data
    payload = json.loads(msg.payload.decode('utf-8'))
    latest_data.update(payload)
    print(f"Received data: {payload}")

def read_demo_data(csv_file):
    global publish_flag, latest_data
    df = pd.read_csv(csv_file)
    
    for index, row in df.iterrows():
        if not publish_flag:
            print("Publishing stopped.")
            break
        
        payload = row.to_dict()
        client.publish(config['mqtt_topic'], json.dumps(payload))
        
        latest_data.update(payload)
        
        print(f"Publishing row {index+1}/{len(df)} to MQTT: {payload}")
        
        time.sleep(config['update_interval'])
    
    if publish_flag:
        print("Finished publishing all rows.")

@app.callback(
    Output('demo-controls', 'children'),
    Input('read-demo-data-toggle', 'value')
)
def toggle_demo_controls(read_demo_data_value):
    if 'read_demo' in read_demo_data_value:
        return html.Div([
            html.Button('Start', id='start-btn', n_clicks=0, style={'padding': '5px 15px', 'backgroundColor': '#28a745', 'color': 'white', 'border': 'none', 'borderRadius': '5px'}),
            html.Button('Stop', id='stop-btn', n_clicks=0, style={'padding': '5px 15px', 'backgroundColor': '#dc3545', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'marginLeft': '10px'})
        ], style={'display': 'inline-block', 'margin': '20px'})
    else:
        # No buttons displayed for real data mode, just a message
        return html.Div("Real data mode is active. Waiting for MQTT data...", style={'fontSize': '18px', 'color': '#555'})

@app.callback(
    Output('start-btn', 'disabled'),
    Output('stop-btn', 'disabled'),
    Input('start-btn', 'n_clicks'),
    Input('stop-btn', 'n_clicks'),
    State('read-demo-data-toggle', 'value')
)
def control_publishing(start_clicks, stop_clicks, read_demo_data_value):
    global publish_flag, publish_thread
    ctx = dash.callback_context

    if not ctx.triggered:
        return False, True
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if 'read_demo' in read_demo_data_value:
        if button_id == 'start-btn' and start_clicks > 0:
            publish_flag = True
            publish_thread = threading.Thread(target=read_demo_data, args=(config['csv_file_path'],))
            publish_thread.start()
            return True, False
        elif button_id == 'stop-btn' and stop_clicks > 0:
            publish_flag = False
            if publish_thread:
                publish_thread.join()
            return False, True
    
    return False, True

def main():
    # Start the MQTT client if not in demo mode
    if not config['read_demo_data']:
        client.on_message = on_message
        client.connect(config['mqtt_broker'], config['mqtt_port'], 60)
        client.subscribe(config['mqtt_topic'])
        client.loop_start()
    
    app.run_server(debug=True)

if __name__ == '__main__':
    main()

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

def create_graph(value, title, graph_type, min_val=0, max_val=100, color="darkblue"):
    if not color or len(color) < 3:
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
    return go.Figure()  # Default empty figure

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

def get_all_gauges():
    if 'dashboard_groups' in config:
        return [gauge for group in config['dashboard_groups'] for gauge in group['gauges']]
    elif 'dashboard_gauges' in config:
        return config['dashboard_gauges']
    else:
        print("Error: Neither 'dashboard_groups' nor 'dashboard_gauges' found in config")
        return []

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
        
        # Update the config file
        if 'dashboard_groups' in config:
            for group in config['dashboard_groups']:
                for gauge in group['gauges']:
                    if gauge['value_key'] == gauge_index:
                        gauge.update(current_settings[gauge_index])
        elif 'dashboard_gauges' in config:
            for gauge in config['dashboard_gauges']:
                if gauge['value_key'] == gauge_index:
                    gauge.update(current_settings[gauge_index])
        else:
            print("Error: Neither 'dashboard_groups' nor 'dashboard_gauges' found in config")
            return dash.no_update

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)

    return current_settings
def update_dashboard(gauge_settings, input_values):
    if 'dashboard_groups' in config:
        # New grouped format
        groups = []
        for group in config['dashboard_groups']:
            graphs = create_graphs_for_group(group, gauge_settings, input_values)
            group_div = html.Div([
                html.H2(group['name'], style={'textAlign': 'center', 'color': '#333', 'marginBottom': '20px'}),
                html.Div(graphs, style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'center'})
            ], style={'width': '100%', 'marginBottom': '40px', 'backgroundColor': '#f9f9f9', 'padding': '20px', 'borderRadius': '10px'})
            groups.append(group_div)
        return groups
    else:
        # Old flat format
        graphs = create_graphs_for_group({'gauges': config['dashboard_gauges']}, gauge_settings, input_values)
        return html.Div(graphs, style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'center'})

def create_graphs_for_group(group, gauge_settings, input_values):
    graphs = []
    for gauge in group['gauges']:
        value_key = gauge['value_key']
        value = latest_data.get(value_key, 0)
        
        settings = gauge_settings.get(value_key, {})
        title = input_values.get(value_key, {}).get('title', gauge['title'])
        min_val = input_values.get(value_key, {}).get('min_val', gauge.get('min_val', 0))
        max_val = input_values.get(value_key, {}).get('max_val', gauge.get('max_val', 100))
        color = input_values.get(value_key, {}).get('color', gauge.get('color', 'darkblue'))
        graph_type = input_values.get(value_key, {}).get('graph_type', 'Gauge')

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
                        {'label': 'Bar', 'value': 'Bar'}
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

def create_graphs_for_group(group, gauge_settings, input_values):
    graphs = []
    for gauge in group['gauges']:
        value_key = gauge['value_key']
        value = latest_data.get(value_key, 0)
        
        settings = gauge_settings.get(value_key, {})
        title = input_values.get(value_key, {}).get('title', gauge['title'])
        min_val = input_values.get(value_key, {}).get('min_val', gauge.get('min_val', 0))
        max_val = input_values.get(value_key, {}).get('max_val', gauge.get('max_val', 100))
        color = input_values.get(value_key, {}).get('color', gauge.get('color', 'darkblue'))
        graph_type = input_values.get(value_key, {}).get('graph_type', 'Gauge')

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
                        {'label': 'Bar', 'value': 'Bar'}
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
    latest_data.update(payload)  # Update the latest data for the dashboard
    print(f"Received data: {payload}")

def read_demo_data(excel_file):
    global publish_flag, latest_data
    try:
        df = pd.read_excel(excel_file, skiprows=11)
    except FileNotFoundError as e:
        print(f"File not found: {excel_file}")
        return
    
    client.connect(config['mqtt_broker'], config['mqtt_port'], 60)
    
    # Create a mapping of Excel column names to config keys
    column_mapping = {
        'V1(V)': 'V1(V)',
        'V2(V)': 'V2(V)',
        'V3(V)': 'V3(V)',
        'A1(A)': 'A1(A)',
        'A2(A)': 'A2(A)',
        'A3(A)': 'A3(A)',
        'P1(KW)': 'P1(KW)',
        'P2(KW)': 'P2(KW)',
        'P3(KW)': 'P3(KW)',
        'PG_V1(V)':'PG_V1(V)',
        'PG_V2(V)':'PG_V2(V)',
        'PG_V3(V)':'PG_V3(V)',
        'PG_A1(A)':'PG_A1(A)',
        'PG_A2(A)':'PG_A2(A)',
        'PG_A3(A)':'PG_A3(A)',
        'PG_P1(KW)':'PG_P1(KW)',
        'PG_P2(KW)':'PG_P2(KW)',
        'PG_P3(KW)':'PG_P3(KW)',
        'L_P1(KWh)':'L_P1(KWh)',
        'L_P2(KWh)':'L_P2(KWh)',
        'L_P3(KWh)':'L_P3(KWh)',
    }
    
    # Get all gauges using the helper function
    all_gauges = get_all_gauges()
    
    for index, row in df.iterrows():
        if not publish_flag:
            print("Publishing stopped.")
            break
        
        payload = {}
        for gauge in all_gauges:
            value_key = gauge['value_key']
            if value_key in column_mapping and column_mapping[value_key] in row:
                payload[value_key] = row[column_mapping[value_key]]
        
        if payload:
            client.publish(config['mqtt_topic'], json.dumps(payload))
            latest_data.update(payload)
            print(f"Publishing row {index+1}/{len(df)} to MQTT: {payload}")
        else:
            print(f"Skipping row {index+1}/{len(df)}: No matching data found")
        
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
    if not config['read_demo_data']:  # If real-time data mode
        client.on_message = on_message  # Define the on_message handler
        client.connect(config['mqtt_broker'], config['mqtt_port'], 60)  # Connect to HiveMQ
        client.subscribe(config['mqtt_topic'])  # Subscribe to the MQTT topic
        client.loop_start()  # Start the MQTT loop
    
    app.run_server(debug=True)  # Start the Dash app

if __name__ == '__main__':
    main()
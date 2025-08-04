import pdb
import sys
import redis
import ast
import time
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go

reference_voltage = 1.2503222670167748
mvpkg = 10.7
lbspkg = 2.2
kgplb = 0.453592

max_size = 10000
# Initialize data lists
data_time = [time.time()]
data_net_counts = [0]
data_revolutions = [0]
data_tension = [0]

def calibrate_tension(x):
    dV = reference_voltage - x
    dmV = dV * 1000
    kgs = (0.1691 * dmV) + 0.0995
    lbs = (0.3728 * dmV) - 0.2193
    return kgs, lbs

def read_and_plot_logger_data():
    # Connect to Redis
    r = redis.Redis(host='localhost', port=6379, db=0)

    # Clear the Redis queue to ensure no stale data
    r.delete('encoder_data')

    # Initialize Dash app
    app = dash.Dash(__name__)

    # Set up the layout
    app.layout = html.Div([
        dcc.Graph(id='live-graph', animate=True),
        dcc.Interval(
            id='graph-update',
            interval=1*100,  # Update every second
            n_intervals=0
        )
    ])

    @app.callback(
        Output('live-graph', 'figure'),
        [Input('graph-update', 'n_intervals')]
    )
    def update_graph(n):
        global data_time, data_net_counts, data_revolutions, data_tension

        # Read data from Redis queue
        data = r.lpop('encoder_data')
        if data:
            # Decode the data from bytes to string
            data = data.decode('utf-8')
            data_array = ast.literal_eval(data)

            timestamp = data_array[0]
            net_counts = data_array[1]
            revolutions = data_array[2]
            tension = calibrate_tension(data_array[3])[0]

            current_time = time.time()
            if int((int(current_time) - current_time) * 1000) % 500 == 0:  # Check if timestamp reaches the half a second mark
                # Append the new data to the lists
                data_time.append(timestamp)
                data_net_counts.append(net_counts)
                data_revolutions.append(revolutions)
                data_tension.append(tension)

                # Keep only the last 10,000 values
                data_time = data_time[-max_size:]
                data_net_counts = data_net_counts[-max_size:]
                data_revolutions = data_revolutions[-max_size:]
                data_tension = data_tension[-max_size:]

        # Create traces
        trace_net_counts = go.Scatter(x=data_time, y=data_net_counts, mode='lines', name='Net Counts')
        trace_revolutions = go.Scatter(x=data_time, y=data_revolutions, mode='lines', name='Revolutions')
        trace_tension = go.Scatter(x=data_time, y=data_tension, mode='lines', name='Tension')

        # Check if data lists are not empty before updating the layout
        if data_time:
            xaxis_range = [min(data_time), max(data_time)]
            yaxis_range = [min(data_net_counts + data_revolutions + data_tension), max(data_net_counts + data_revolutions + data_tension)]
        else:
            xaxis_range = [0, 1]
            yaxis_range = [0, 1]

        return {
            'data': [trace_net_counts, trace_revolutions, trace_tension],
            'layout': go.Layout(
                title='Real-time Data Plotting',
                xaxis=dict(range=xaxis_range),
                yaxis=dict(range=yaxis_range),
            )
        }

    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=8050, debug=True)

if __name__ == "__main__":
    read_and_plot_logger_data()
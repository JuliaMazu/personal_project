from dash import Dash, html

# Initialize the Dash app
app = Dash(__name__)
server = app.server
# Define the layout of the app
app.layout = html.Div(children=[
    html.H1(children='Hello User')
])


# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
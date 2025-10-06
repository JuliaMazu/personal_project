from dash import Dash, html
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import pandas as pd
import dash
from dash import dcc, html, Input, Output, State, clientside_callback, Patch
from dash_chat import ChatComponent
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import load_figure_template
from agent import graph
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage



# Initialize the Dash app
app = Dash(__name__, external_stylesheets=[dbc.themes.ZEPHYR, dbc.icons.FONT_AWESOME])
server = app.server

origins = [
    'https://JuliaMazu.github.io',  # Adresse GitHub Pages, à modifier avec votre identifiant github
    'http://localhost:8050'          # autorise les tests locaux
]

"""server.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=['*'],
    allow_headers=['*'],
    max_age=3600
)"""

# Define the layout of the app/Users/yulenka/Documents/data/neo4j-agent/neo4j-client/.env
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(
            html.H1("Sport NutriBites", className="text-center"),
            width=12,
            className="py-3" # Add some vertical padding
        )
    ], className="mb-4 mt-4 border-bottom"),
    
    dbc.Row(
    [           dcc.Store(id='session-store', data={'thread_id': None}),
                ChatComponent(
                    id="chat-component",
                    messages=[],
                    theme="dark",
                    input_placeholder="Which factors affect iron absorbtion",
                    container_style={"height": "60vh",
                                     "width": "50%"},
                    user_bubble_style={"background-color": "#42C4F7"},
                    assistant_bubble_style={"background-color": "#E0E0E0"},
                    input_text_style={"background-color": "#E0E0E0"}
                )
            ],
            className="d-flex justify-content-center")
], fluid=True)

@app.callback(
    Output("chat-component", "messages"),
    Output("session-store", "data"),
    Input("chat-component", "new_message"),
    State("chat-component", "messages"),
    State("session-store", "data"),
    prevent_initial_call=True,
)
def handle_chat(new_message, messages, session_data):

    thread_id = session_data.get('thread_id')
    if thread_id is None:
        thread_id = str(uuid.uuid4())  # Generate a new unique ID
        session_data['thread_id'] = thread_id

    if not new_message:
        return messages

    updated_messages = messages + [new_message]

    if new_message["role"] == "user":
        config = {"configurable": {"thread_id": thread_id}}
        initial_message = HumanMessage(content=new_message["content"])
        response = graph.invoke({"messages" : [{"role": new_message["role"], 
                                  "content": new_message["content"]}]}      
                                ,config=config)
            
        bot_response = {"role": "assistant", "content": response['messages'][-1].content}
        return updated_messages + [bot_response], session_data

    return updated_messages, session_data

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
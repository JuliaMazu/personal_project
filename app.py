from dash import Dash, html
from flask import Flask, request, jsonify
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

from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import base64

from dotenv import load_dotenv
#load_dotenv() 


# Initialize the Dash app
app = Dash(__name__, external_stylesheets=[dbc.themes.ZEPHYR, dbc.icons.FONT_AWESOME])
server = app.server

origins = [
    'https://JuliaMazu.github.io',  # Adresse GitHub Pages, à modifier avec votre identifiant github
    'http://localhost:8050'          # autorise les tests locaux
]

@server.after_request
def add_cors_headers(response):
    # Determine the origin of the request
    origin = request.headers.get('Origin')
    
    # Check if the origin is allowed
    if origin in origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Headers'] = '*'
        response.headers['Access-Control-Allow-Methods'] = '*'
        response.headers['Access-Control-Max-Age'] = '3600'
    
    # Handle preflight (OPTIONS) requests
    if request.method == 'OPTIONS':
        response = server.response_class()
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Headers'] = '*'
        response.headers['Access-Control-Allow-Methods'] = '*'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response
        
    return response



def image_generate(answer):
    client = genai.Client(api_key = os.getenv("GEMINI_IMAGE"))

    prompt = (f"create an image of schema or an explanation of this text that summarize and improves comprehension text: {answer}")

    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[prompt],
    )

    for part in response.candidates[0].content.parts:
        if part.text is not None:
            print(part.text)
        elif part.inline_data is not None:
            image = Image.open(BytesIO(part.inline_data.data))
            #image.save("generated_image.png")
    return image

def pil_to_base64(img):
    """Converts a PIL Image object to a base64 string for Dash display."""
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{encoded_image}"

chat_component = ChatComponent(
                    id="chat-component",
                    messages=[],
                    theme="dark",
                    input_placeholder="Which factors affect iron absorption",
                    # container_style is often better managed with className and a width on dbc.Col
                    container_style={"height": "60vh"}, 
                    user_bubble_style={"background-color": "#42C4F7"},
                    assistant_bubble_style={"background-color": "#E0E0E0"},
                    input_text_style={"background-color": "#E0E0E0"}
                )
                ###layout
# Assuming all necessary components are imported: dbc, dcc, html, ChatComponent

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(
            html.H1("Sport NutriBites for Internal use", className="text-center"),
            width=12,
            className="py-3"
        )
    ], className="mb-4 mt-4 border-bottom"),
    
    dbc.Row([
        dbc.Col( 
            [dcc.Store(id='session-store', data={'thread_id': None}),
            chat_component
            ],
            width=6   
        ),
        dbc.Col([
         html.Div(id='output-image-container', children=[
        html.Img(id='generated-image-display', style={'max-width': '100%', 'border': '1px solid #ccc'})
                ])],
        width=6 )
        ]
    )
], fluid=True)

@app.callback(
    Output("chat-component", "messages"),
    Output("session-store", "data"),
    Output('generated-image-display', 'src'),
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
        response = graph.invoke({"messages" : [{"role": new_message["role"], 
                                  "content": new_message["content"]}]}      
                                ,config=config)
            
        bot_response = {"role": "assistant", "content": response['messages'][-1].content}
        pil_img = image_generate(bot_response)
        base64_src = pil_to_base64(pil_img)
        return updated_messages + [bot_response], session_data, base64_src

    return updated_messages, session_data


# Run the app
if __name__ == '__main__':
    app.run(debug=True)
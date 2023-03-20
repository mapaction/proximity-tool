"""Module for openrouteservice-related functionalities."""
import os

import streamlit as st
from dotenv import load_dotenv
from openrouteservice import client
from src.utils import is_app_on_streamlit

load_dotenv()


def ors_initialize():
    """Initialise OpenRouteService with the API key."""
    if is_app_on_streamlit():
        api_key = st.secrets["ors_api"]
    else:
        api_key = os.getenv("API_KEY")
    return client.Client(key=api_key)

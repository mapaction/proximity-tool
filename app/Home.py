"""Home page for Streamlit app."""
import streamlit as st
from src.config_parameters import params
from src.utils import (
    add_about,
    add_logo,
    set_home_page_style,
    toggle_menu_button,
)

# Page configuration
st.set_page_config(layout="wide", page_title=params["browser_title"])

# If app is deployed hide menu button
toggle_menu_button()

# Create sidebar
add_logo("app/img/MA-logo.png")
add_about()

# Set page style
set_home_page_style()

# Page title
st.markdown("# Home")

# First section
st.markdown("## Introduction")
st.markdown(
    """
    This web app allows you to upload POIs and generate isochrones of
    travel time.
"""
)

# Second section
st.markdown("## How to use the tool")

"""Flood extent analysis page for Streamlit app."""
import streamlit as st
from src.config_parameters import params
from src.utils import (
    add_about,
    add_logo,
    set_tool_page_style,
    toggle_menu_button,
)

# Page configuration
st.set_page_config(layout="wide", page_title=params["browser_title"])

# If app is deployed hide menu button
toggle_menu_button()

# Create sidebar
add_logo("app/img/MA-logo.png")
add_about()

# Page title
st.markdown("# Tool title")

# Set page style
set_tool_page_style()


# Create app
def app():
    """Create Streamlit app."""
    pass


# Run app
app()

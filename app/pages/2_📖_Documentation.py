"""Documentation page for Streamlit app."""
import streamlit as st
from src.config_parameters import params
from src.utils import (
    add_about,
    add_logo,
    set_doc_page_style,
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
set_doc_page_style()

# Page title
st.markdown("# Documentation")

# First section
st.markdown("## Methodology")

# Second section
st.markdown("## Radar imagery for flood detection")

# Third section
st.markdown("## Key limitations")

# Last section
st.markdown("## Useful links")

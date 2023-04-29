"""Proximity analysis page for Streamlit app."""
import streamlit as st
from src.config_parameters import params
from streamlit_folium import st_folium
from folium.plugins import Draw, Geocoder, MiniMap
from src.utils import (
    add_about,
    add_logo,
    set_tool_page_style,
    toggle_menu_button,
)
from src.utils_plotting import (
    folium_static_with_legend,
    plot_isochrones,
    plot_population_summary,
    draw_aoi,
    create_input_map,
)
from src.utils_proximity import (
    poi_v_aoi,
    process_aoi_data,
    process_poi_data,
    run_analysis,
)

# Page configuration
st.set_page_config(layout="wide", page_title=params["browser_title"])

# If app is deployed hide menu button
toggle_menu_button()

# Create sidebar
add_logo("app/img/MA-logo.png")
add_about()

# Page title
st.markdown("# Proximity analysis")

# Set page style
set_tool_page_style()

# Parameters
verbose = True
use_default_data = True
use_local_pop_data = False

# If using default data, print
if use_default_data:
    st.info("Using default data, no API call will be made.")

# If using local tiff data, print
if use_local_pop_data:
    st.info("Using local tiff data, no WorldPop API will be used.")

# Set initial stage to 0
if "stage" not in st.session_state:
    st.session_state.stage = 0


# Define function to change stage
def set_stage(stage):
    """
    Set stage for the app.

    Each time a certain button is pressed, the stage progresses by one.
    """
    st.session_state.stage = stage


# Create file uploader object for POIs
upload_poi_file = st.file_uploader(
    "Upload a zipped shapefile containing your POIs",
    type=["zip"],
    on_change=set_stage,
    args=(1,),
)

# Add AOI
if st.session_state.stage > 0:
    aoi_gdf = None
    upload_aoi_file = ""
    if st.checkbox(
        "Fill gaps using an Area of Interest file?",
        on_change=set_stage,
        args=(1,),
    ):
        # Create file uploader object for AOI
        upload_aoi_file = st.file_uploader(
            "Upload a zipped shapefile delineating your Area of Interest or Draw your AOI on the map below",
            type=["zip"],
            on_change=set_stage,
            args=(1,),
        )
        # Draw own AOI
        with st.expander("Or want to draw your AOI on the map below?", expanded=True):
            map2 = draw_aoi(poi=upload_poi_file)
            output = st_folium(map2, width='100%', height=600)
        # Check if AOI drawn
        if "all_drawings" in output:
            check_drawing = (output["all_drawings"] != [] and output["all_drawings"] is not None)
        if not check_drawing:
            st.write("No AOI drawn yet.")
        else:
            coords = output["all_drawings"][-1]["geometry"]["coordinates"][0]
            st.write("AOI drawn successfully!")
            st.write(coords)
    st.button("Check input data?", on_click=set_stage, args=(2,))

# Check input data
if st.session_state.stage > 1:
    try:
        poi_gdf, in_poi_flds, valid_geom = process_poi_data(upload_poi_file)
        if not valid_geom:
            st.error(
                "The POI shapefile contains geometries that are not "
                "points. Check the source data."
            )
            st.stop()

    except Exception:
        st.error(
            "Error with importing the POI shapefile. Check the source data."
        )
        st.stop()
    else:
        if upload_aoi_file:
            try:
                aoi_gdf, valid_geom = process_aoi_data(upload_aoi_file)
                if not valid_geom:
                    st.error(
                        "The AOI shapefile contains geometries that are not "
                        "polygons. Check the source data."
                    )
                    st.stop()
                poi_within_aoi, poi_outside_aoi = poi_v_aoi(aoi_gdf, poi_gdf)
                st.write(
                    """
                    There are %s points inside the AOI, and %s outside.
                    """
                    % (poi_within_aoi, poi_outside_aoi)
                )
            except Exception:
                st.error(
                    "Error with importing the AOI shapefile. Check the source "
                    "data."
                )
                st.stop()
        else:
            st.write("No AOI dataset uploaded yet.")
        st.write(
            "If you are happy to proceed, select the column of the POI "
            "dataset that defines the names of the locations: this "
            "information will be used when plotting the isochrones. Also, "
            "tick the box if you want to include population data in the "
            "analysis. "
            "Finally click on the button 'Ready to run?'."
        )
        poi_name_col = st.selectbox(
            "Select the label field in your POI dataset", in_poi_flds
        )
        add_pop_data = st.checkbox(
            "Add population data to the analysis",
            on_change=set_stage,
            args=(2,),
        )
        st.success("You are ready to create the isochrones.")
        st.button("Ready to run?", on_click=set_stage, args=(3,))

# Run computations
if st.session_state.stage > 2:
    with st.spinner("Computing... Please wait..."):
        # run analysis
        isochrones = run_analysis(
            poi_gdf=poi_gdf,
            poi_name_col=poi_name_col,
            aoi_gdf=aoi_gdf,
            use_default_data=use_default_data,
            add_pop_data=add_pop_data,
            use_local_pop_data=use_local_pop_data,
            verbose=verbose,
            text_on_streamlit=True,
        )

        # map results
        map1 = plot_isochrones(
            gdf=isochrones, poi_gdf=poi_gdf, poi_name_col=poi_name_col
        )
        folium_static_with_legend(map1, isochrones, "Travel time")
        if add_pop_data:
            fig = plot_population_summary(isochrones)
            st.pyplot(fig)
        st.success("Computation complete")

    st.button("Reset", on_click=set_stage, args=(0,))

"""Proximity analysis page for Streamlit app."""
import folium
import streamlit as st
from src.config_parameters import params
from src.utils import (
    add_about,
    add_logo,
    set_tool_page_style,
    toggle_menu_button,
)
from src.utils_proximity import (
    difference_iso,
    dissolve_iso,
    fill_aoi,
    get_isochrones,
    prep_user_poi,
)
from src.utils_user_input import (
    create_aoi_gpd,
    create_poi_gpd,
    get_poi_flds,
    poi_v_aoi,
)
from streamlit_folium import folium_static

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

# Create file uploader object for POIs
upload_poi_file = st.file_uploader(
    "Upload a zipped shapefile containing your POIs", type=["zip"]
)

upload_aoi_file = ""  # stops warning at run time TO DO: handle this better
if st.checkbox("Fill gaps using an Area of Interest file?"):
    # Create file uploader object for AOI
    upload_aoi_file = st.file_uploader(
        "Upload a zipped shapefile delineating your Area of Interest",
        type=["zip"],
    )

if upload_poi_file:
    poi_gdf = create_poi_gpd(upload_poi_file)
    in_poi_flds = get_poi_flds(poi_gdf)
    poi_name_col = st.selectbox(
        "Select the label field in your POI dataset", in_poi_flds
    )

if upload_aoi_file:
    aoi_gdf = create_aoi_gpd(upload_aoi_file)

if st.button("Check input data?"):
    if upload_aoi_file:
        poi_within_aoi, poi_outside_aoi = poi_v_aoi(aoi_gdf, poi_gdf)
        st.write(
            """
            There are %s points inside the AOI, and %s outside.
            If you are happy to proceed click Ready to Run button

            """
            % (poi_within_aoi, poi_outside_aoi)
        )
    else:
        st.write("No AOI dataset uploaded yet")

if st.button("Ready to run?"):
    # prepare start points
    data_prep_state = st.text("Preparing start points...")
    start_points_dict, map_centre = prep_user_poi(poi_gdf, poi_name_col)
    data_prep_state.text(f"Running on {len(start_points_dict)} start points.")

    # run API calls
    api_call_state = st.text(
        "Starting API calls, this could take a few minutes..."
    )
    all_isos, api_time = get_isochrones(start_points_dict)
    api_call_state.text(f"Completed API calls in {round(api_time, 2)} seconds")

    # dissolve isochrones
    diss_isos_state = st.text("Dissolving isochrones...")
    diss_isoc, diss_time = dissolve_iso(all_isos)
    diss_isos_state.text(
        f"Completed dissolve in {round(diss_time, 2)} seconds"
    )

    # get diffs (i.e. remove overlaps)
    diff_isos_state = st.text("Removing overlapping isochrones...")
    diff_isoc, diff_time = difference_iso(diss_isoc)
    diff_isos_state.text(
        f"Completed overlap removal in {round(diff_time, 2)} seconds"
    )

    # fill to aoi area
    fill_aoi_state = st.text("Filling AOI areas outside isochrones...")
    filled_to_aoi, fill_time = fill_aoi(diff_isoc, aoi_gdf)
    fill_aoi_state.text(f"Filled AOI area in {round(fill_time, 2)} seconds")
    mapable = "Yes"

    # save geopackage of final output
    save_output_state = st.text("saving output to gpkg...")
    # filled_to_aoi.to_file(
    #     os.path.join(final_output_folder, output_gpkg), driver="GPKG"
    #     )
    # save_output_state.text(f'Saved {output_gpkg} to {final_output_folder}.')

    # map results
    map1 = folium.Map(
        tiles="CartoDB Positron", location=(map_centre), zoom_start=7
    )
    # add start points to map
    for name, start_pt in start_points_dict.items():
        # reverse coords due to folium lat/lon syntax
        folium.map.Marker(
            list(reversed(start_pt["location"])),
            icon=folium.Icon(
                color="blue",
                icon_color="#cc0000",
                icon="home",
                prefix="fa",
            ),
            popup=name,
        ).add_to(map1)
    # TODO: need to make this robust to handle different user input parameters;
    interval_to_colour = {
        "0 - 900": "#1a9641",
        "900 - 1800": "#a6d96a",
        "1800 - 2700": "#fdae61",
        "2700 - 3600": "#d7191c",
        "> 3600": "#68507b",
    }

    def style_function(feature):
        """Add docstrings here."""
        return {
            "fillopacity": 1,
            "weight": 1,
            "color": interval_to_colour[feature["properties"]["interval"]],
        }

    # TODO: add popups for isochrones
    # TODO: add layer names to each geojson based on interval
    # add processed isochrones
    for i in range(len(filled_to_aoi)):
        geo_j = filled_to_aoi.iloc[[i]].to_json()
        geo_j = folium.GeoJson(data=geo_j, style_function=style_function)
        geo_j.add_to(map1)
    folium.LayerControl().add_to(map1)

    folium_static(map1)

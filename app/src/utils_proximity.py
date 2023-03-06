"""Functions for proximity analysis."""
import time
import typing
from itertools import islice
from timeit import default_timer

import branca
import fiona
import folium
import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from folium.plugins import Draw, Geocoder, MiniMap
from geojson.geometry import Polygon
from src.utils_ors import ors_initialize

# TODO: let the user select this. Some choices depend on previous choices
params_iso = {
    "profile": "driving-car",
    "range": [900, 1800, 2700, 3600],  # 900/60 = 15 minutes,
    "range_type": "time",
    "attributes": ["total_pop"],  # Get pop count for isochrones
}

# TODO: assign to user parameter
save_to_file = False


def create_poi_gpd(in_poi_file):
    """Read a point-of-interest GeoJSON file and returns a GeoDataFrame.

    Inputs
    ----------
    in_poi_file (str): input file path of the point-of-interest
        GeoJSON file.

    Returns
    -------
    in_poi_gdf (geopandas.GeoDataFrame): point-of-interest GeoDataFrame.
    """
    in_poi_gdf = gpd.read_file(in_poi_file)
    return in_poi_gdf


def check_poi_geometry(poi_gdf):
    """Check whether all geometries are points.

    Inputs
    ----------
    poi_gdf (geopandas.GeoDataFrame): point-of-interest GeoDataFrame.

    Returns
    -------
    (bool): True if all geometries are points, False otherwise.
    """
    return all([geom == "Point" for geom in poi_gdf.geom_type.tolist()])


def create_aoi_gpd(in_aoi_file):
    """Read an area-of-interest GeoJSON file and returns a GeoDataFrame.

    Inputs
    ----------
    in_aoi_file (str): input file path of the area-of-interest GeoJSON
        file.

    Returns
    -------
    in_aoi_gdf (geopandas.GeoDataFrame): area-of-interest GeoDataFrame.
    """
    in_aoi_gdf = gpd.read_file(in_aoi_file)
    return in_aoi_gdf


def check_aoi_geometry(aoi_gdf):
    """Check whether all geometries are polygons.

    Inputs
    ----------
    poi_gdf (geopandas.GeoDataFrame): area-of-interest GeoDataFrame.

    Returns
    -------
    (bool): True if all geometries are polygons, False otherwise.
    """
    return all(["Polygon" in geom for geom in aoi_gdf.geom_type.tolist()])


# get field names in user uploaded POI dataset
def get_poi_flds(poi_gdf):
    """Return the list of field names in the point-of-interest GeoDataFrame.

    Inputs
    ----------
    poi_gdf (geopandas.GeoDataFrame): point-of-interest GeoDataFrame.

    Returns
    -------
    in_poi_flds (list of str): list of field names in the point-of-interest
        GeoDataFrame.
    """
    # in_poi = gpd.read_file(poi_file)
    in_poi_flds = list(poi_gdf.columns)
    return in_poi_flds


# # check number of POI inside and outside of AOI
def poi_v_aoi(aoi_gdata, poi_gdata):
    """
    Return the numbers of POIs within and outside of the AOI.

    Inputs
    ----------
    aoi_gdata (geopandas.GeoDataFrame): area-of-interest GeoDataFrame.
    poi_gdata (geopandas.GeoDataFrame): point-of-interest GeoDataFrame.

    Returns
    -------
    poi_within_aoi (int): number of point-of-interests within the
        area-of-interest.
    poi_outside_aoi (int): number of point-of-interests outside of the
        area-of-interest.
    """
    aoi_sgl = aoi_gdata.geometry.unary_union  # ensure a single aoi poly
    poi_within_aoi = poi_gdata[poi_gdata.geometry.within(aoi_sgl)].shape[0]
    poi_outside_aoi = poi_gdata[~poi_gdata.geometry.within(aoi_sgl)].shape[0]
    return poi_within_aoi, poi_outside_aoi


def run_analysis(
    poi_gdf,
    poi_name_col,
    aoi_gdf,
    use_default_data,
    verbose=False,
    text_on_streamlit=True,
):
    """
    Run the whole analysis, and find isochrones.

    The function uses the given POI and AOI geodataframes to generate
    isochrones, removes overlapping isochrones and fills AOI areas outside
    the isochrones if an AOI file has been uploaded. Finally, it saves the
    geopackage of the final output.

    Inputs
    ----------
    poi_gdf (geopandas.geodataframe.GeoDataFrame): Geodataframe containing
        points of interest
    poi_name_col (str): Name of the column containing POI names
    aoi_gdf (geopandas.geodataframe.GeoDataFrame): Geodataframe containing the
        area of interest
    use_default_data (bool) If True, load the isochrones from file
        instead of using the OpenRouteServiec API.
    verbose (bool, optional): if True, print details run. Defaults to False.
    text_on_streamlit (str, optional): if True, print text in the Streamlit app
        via st.write(), otherwise print to console. Defaults to True.

    Returns
    -------
    diff_isoc (geopandasGeoDataFrame): Geodataframe containing the final output
        after removing overlapping isochrones and filling AOI areas outside the
        isochrones if an AOI file has been uploaded.
    """
    # Prepare start points
    mock_st_text(
        "Preparing start points...",
        verbose=verbose,
        text_on_streamlit=text_on_streamlit,
    )
    start_points_dict, map_centre = prep_user_poi(poi_gdf, poi_name_col)
    mock_st_text(
        f"Running on {len(start_points_dict)} start points.",
        verbose=verbose,
        text_on_streamlit=text_on_streamlit,
    )

    # Initiate ors client
    ors = ors_initialize()

    # Run API calls
    mock_st_text(
        "Starting API calls, this could take a few minutes...",
        verbose=verbose,
        text_on_streamlit=text_on_streamlit,
    )
    all_isos, api_time = get_isochrones(
        start_points_dict, ors, mock_function=use_default_data
    )
    mock_st_text(
        f"Completed API calls in {round(api_time, 2)} seconds",
        verbose=verbose,
        text_on_streamlit=text_on_streamlit,
    )

    # Dissolve isochrones
    mock_st_text(
        "Dissolving isochrones...",
        verbose=verbose,
        text_on_streamlit=text_on_streamlit,
    )
    diss_isoc, diss_time = dissolve_iso(all_isos)
    mock_st_text(
        f"Completed dissolve in {round(diss_time, 2)} seconds",
        verbose=verbose,
        text_on_streamlit=text_on_streamlit,
    )

    # Remove isochrones overlaps
    mock_st_text(
        "Removing overlapping isochrones...",
        verbose=verbose,
        text_on_streamlit=text_on_streamlit,
    )
    diff_isoc, diff_time = difference_iso(diss_isoc)
    mock_st_text(
        f"Completed overlap removal in {round(diff_time, 2)} seconds",
        verbose=verbose,
        text_on_streamlit=text_on_streamlit,
    )

    # Fill to aoi area
    if aoi_gdf is not None:
        mock_st_text(
            "Filling AOI areas outside isochrones...",
            verbose=verbose,
            text_on_streamlit=text_on_streamlit,
        )
        diff_isoc, fill_time = fill_aoi(diff_isoc, diss_isoc, aoi_gdf)
        mock_st_text(
            f"Filled AOI area in {round(fill_time, 2)} seconds",
            verbose=verbose,
            text_on_streamlit=text_on_streamlit,
        )

    # TODO: to be implemented, maybe not in this function, but after the
    #       rendering of the map
    # Save geopackage of final output
    # if save_to_file:
    #     mock_st_text(text_field, "saving output to gpkg...")
    #     diff_isoc.to_file(
    #         os.path.join(final_output_folder, output_gpkg), driver="GPKG"
    #         )
    #     mock_st_text(
    #         text_field,
    #         f'Saved {output_gpkg} to {final_output_folder}.'
    #         )

    return diff_isoc


def mock_st_text(text, verbose, text_on_streamlit):
    """
    Return streamlit text using a given text object.

    If the object is None, return None. This function can be used in streamlit
    or in jupyter notebook.

    Inputs
    ----------
    text (str): text to display.
    verbose (bool): if True, print details run.
    text_on_streamlit (str): if True, print text in the Streamlit app
        via st.write(), otherwise print to console.

    Returns
    -------
    None or the updated text_field.
    """
    if not verbose:
        return
    if text_on_streamlit:
        st.write(text)
    else:
        print(text)


def color_list_from_cmap(cmap_name, n):
    """
    Generate a list of n colors from a specified color map.

    Inputs
    ----------
    cmap_name (str): name of the color map to use. This should be a valid
    color map name recognized by matplotlib.cm.get_cmap().

    n (int): number of colors to generate in the color list.

    Returns
    -------
    color_list (list of str): A list of n colors represented as hexadecimal
        strings.
    """
    cmap = matplotlib.cm.get_cmap(cmap_name)
    color_list = cmap(np.array(np.rint(np.linspace(0, cmap.N, n)), dtype=int))
    return [matplotlib.colors.to_hex(c) for c in color_list]


def check_label_poi(poi_gdata, label_col):
    """
    Check if the labels in a GeoDataFrame's specified column are hashable.

    Inputs
    ----------
    poi_gdata (geopandas.GeoDataFrame): A GeoDataFrame containing the point-
        of-interest data.
    label_col (str): name of the column containing the label to check.

    Returns
    -------
    is_hashable (bool): True if the label in the first row of the specified
        column is hashable, False otherwise.
    """
    label = poi_gdata[label_col].tolist()[0]
    return isinstance(label, typing.Hashable)


def prep_user_poi(poi_gdata, label_col):
    """
    Prepare start points and map centre for POIs provided in a GeoDataFrame.

    Inputs
    ----------
    poi_gdata (geopandas.GeoDataFrame): GeoDataFrame containing the
        point-of-interest data.
    label_col (str): name of the column containing the POI labels.

    Returns
    -------
    start_points (dict): A dictionary containing the start point locations for
        each POI.
    centre_list (list): A list containing the centroid coordinates of the input
        POIs for use in mapping results.
    """
    start_points = {}
    # get centroid of input POIs; used in mapping results
    map_cent = poi_gdata.dissolve().to_crs("EPSG:4326").centroid
    centre_list = [map_cent.y, map_cent.x]  # reversed for folium

    label = poi_gdata[label_col]
    xcoords = poi_gdata.geometry.x
    ycoords = poi_gdata.geometry.y

    for lab, x, y in zip(label, xcoords, ycoords):
        start_points[lab] = {"location": [x, y]}
    return start_points, centre_list


def chunks(data, chunksize):
    """
    Split a dictionary into chunks of a given size.

    This is done to overcome the restriction of the OpenRouteService API
    (5 isochrones at a time).

    Inputs
    ----------
    data (dict): A dictionary to be split into chunks.
    chunksize (int): size of each chunk.

    Returns
    -------
    A generator that yields dictionaries, where each dictionary contains
    chunksize number of items from the original dictionary. The last dictionary
    may have fewer items if len(data) % chunksize != 0.
    """
    it = iter(data)
    for _ in range(0, len(data), chunksize):
        yield {k: data[k] for k in islice(it, chunksize)}


def get_isochrones(start_points, ors, mock_function=False):
    """
    Perform an isochrone search using OpenRouteService API.

    Inputs
    ----------
    start_points (dict): A dictionary containing the (longitude, latitude)
        coordinates of the starting points for the search.
    ors (object): An OpenRouteService object initialized with an API key.
    mock_function (bool, optional) If True, load the isochrones from file
        instead of using the OpenRouteServiec API. Defaults is False.

    Returns
    -------
    all_isos (geopandas.GeoDataFrame): result of the isochrone search.
    api_time (float): time taken execute the function, in seconds.
    """
    # start timer:
    iso_start = default_timer()
    if mock_function:
        api_time = default_timer() - iso_start
        try:
            all_isos = gpd.read_file("app/test_data/mda_isochrones.geojson")
        except fiona.errors.DriverError:
            all_isos = gpd.read_file("test_data/mda_isochrones.geojson")
        return all_isos, api_time
    # create geodataframe to hold the API responses
    all_isos = gpd.GeoDataFrame(
        columns=[
            "type",
            "properties.group_index",
            "properties.value",
            "properties.center",
            "properties.total_pop",
            "geometry.coordinates",
            "geometry.type",
            "geometry",
            "name",
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )

    for item in chunks(start_points, 5):
        for name, start_pt in item.items():
            # Add coords to request parameters
            params_iso["locations"] = [start_pt["location"]]
            # Perform isochrone request
            start_pt["iso"] = ors.isochrones(**params_iso)

            # convert geoj to gdf
            gdf = gpd.GeoDataFrame.from_dict(
                pd.json_normalize(start_pt["iso"]["features"]),
                orient="columns",
            )
            gdf["geometry"] = gdf["geometry.coordinates"].apply(
                lambda p: Polygon(p)
            )
            gdf["name"] = name
            gdf = gdf.set_crs(epsg=4326)
            # append this response to the dataframe
            all_isos = gpd.GeoDataFrame(
                pd.concat([all_isos, gdf], ignore_index=True), crs=gdf.crs
            )
            # pause for 1.5s
            time.sleep(1.5)
    # clean up some of the column names
    all_isos.rename(
        columns={
            "properties.value": "value",
            "properties.total_pop": "total_pop",
            "geometry.type": "geometry_type",
        },
        inplace=True,
    )
    # remove unwanted columns
    all_isos = all_isos.drop(all_isos.columns[[1, 3, 5]], axis=1)
    iso_end = default_timer()
    api_time = iso_end - iso_start
    return all_isos, api_time


def dissolve_iso(isos):
    """
    Dissolve isochrones by value.

    This allows to create a unique set of isochrones with several points of
    interest.

    Inputs
    ----------
    isos (geopandas.GeoDataFrame): GeoDataFrame containing isochrone data.

    Returns
    -------
    dissolved (geopandas.GeoDataFrame): GeoDataFrame containing dissolved
        isochrones.
    diss_time (float): time taken execute the function, in seconds.
    """
    diss_start = default_timer()
    diss_isoc = isos.dissolve(by="value", as_index=False).reset_index(
        drop=True
    )
    diss_end = default_timer()
    diss_time = diss_end - diss_start
    return diss_isoc, diss_time


def difference_iso(diss_isoc):
    """
    Compute difference between consecutive isochrones.

    The function clips overlapping polygons, to create new non-overlapping
    polygons.

    Inputs
    ----------
    diss_isoc (geopandas.GeoDataFrame): GeoDataFrame containing overlapping
        isochrones.

    Returns
    -------
    diff_isoc (geopandas.GeoDataFrame): GeoDataFrame containing non-overlapping
        isochrones.
    diff_time (float): time taken execute the function, in seconds.
    """
    diff_start = default_timer()
    value_list = diss_isoc["value"].tolist()
    geometry_list = diss_isoc["geometry"].tolist()

    value_new_list = []
    geometry_new_list = []

    for i in range(len(value_list)):
        if i == 0:
            value_new = f"0 - {int(value_list[0])}"
            geometry_new = geometry_list[0]
        else:
            value_new = f"{int(value_list[i-1])} - {int(value_list[i])}"
            geometry_new = geometry_list[i].difference(geometry_list[i - 1])

        value_new_list.append(value_new)
        geometry_new_list.append(geometry_new)

    diff_isoc = gpd.GeoDataFrame(
        list(zip(value_new_list, geometry_new_list)),
        columns=["interval", "geometry"],
    )
    diff_isoc.crs = diss_isoc.crs
    diff_time = default_timer() - diff_start

    return diff_isoc, diff_time


# 3 Fill gaps using AOI
def fill_aoi(diff_isoc, diss_isoc, aoi):
    """
    Fill the space between isochrones and AOI.

    The function adds to the dissolved non-overlapping isochrones a polygon
    given by the difference between the area of interest and the largest
    isochrone.

    Inputs
    ----------
    diff_isoc (geopandas.GeoDataFrame): GeoDataFrame containing the
        non-overlapping isochrones.
    diss_isoc (geopandas.GeoDataFrame): GeoDataFrame containing the overlapping
        isochrones. This is used to make calculations faster.
    aoi (geopandas.GeoDataFrame): GeoDataFrame representing the area of
        interest.

    Returns
    -------
    filled_to_aoi (geopandas.GeoDataFrame): GeoDataFrame containing the
        non-overlapping isochrones, plus a polygon that fills the AOI.
    fill_time (float): time taken execute the function, in seconds.

    """
    fill_start = default_timer()
    geometry_new = (
        aoi["geometry"].iloc[0].difference(diss_isoc["geometry"].iloc[-1])
    )
    interval_new = f"> {int(diss_isoc['value'].iloc[-1])}"

    filled_aoi = gpd.GeoDataFrame(
        [(interval_new, geometry_new)],
        columns=diff_isoc.columns.tolist(),
    )
    filled_aoi.crs = diss_isoc.crs

    filled_to_aoi = pd.concat([diff_isoc, filled_aoi]).reset_index(drop=True)

    fill_time = default_timer() - fill_start

    return filled_to_aoi, fill_time


def folium_static_with_legend(
    fig,
    gdf,
    legend_title,
    cmap_name="viridis",
    width=700,
    height=500,
):
    """
    Create a HTML representation of a Folium map with a categorical legend.

    This function redefines the function folium_static() from the library
    streamlit_folium (https://github.com/randyzwitch/streamlit-folium).

    Inputs
    ----------
    fig (folium.Map, folium.plugins.DualMap, or branca.element.Figure):
        Folium map to be rendered in HTML.
    gdf (geopandas.GeoDataFrame): GeoDataFrame containing the data for
        the categorical legend.
    legend_title (str): title for the categorical legend.
    cmap_name (str, optional): name of the colormap to use for
        the legend. Defaults to 'viridis'.
    width (int, optional): width of the HTML representation, in pixels.
        Defaults to 700.
    height (int, optional): height of the HTML representation, in pixels.
        Defaults to 500.

    Returns
    -------
    output (str) the HTML representation of the Folium map, with the
        categorical legend.
    """
    # if Map, wrap in Figure
    if isinstance(fig, folium.Map):
        fig = folium.Figure().add_child(fig)
        fig = add_categorical_legend(
            fig, title=legend_title, gdf=gdf, cmap_name=cmap_name
        )
        return components.html(
            fig.render(), height=(fig.height or height) + 10, width=width
        )

    # if DualMap, get HTML representation
    elif isinstance(fig, folium.plugins.DualMap) or isinstance(
        fig, branca.element.Figure
    ):
        return components.html(
            fig._repr_html_(), height=height + 10, width=width
        )


def add_categorical_legend(folium_map, title, gdf, cmap_name="viridis"):
    """
    Add a categorical legend to a Folium map.

    Inputs
    ----------
    folium_map (folium.Map): Folium map to add the categorical legend to.
    title (str): title for the categorical legend.
    gdf (geopandas.GeoDataFrame): GeoDataFrame containing the data for the
        categorical legend.
    cmap_name (str, optional): name of the colormap to use for the
        legend. Defaul is 'viridis'.

    Returns
    -------
    folium_map (folium.Map): Folium map with the added categorical legend.
    """
    # create dict colors
    color_by_label = dict(
        zip(
            gdf["interval"].tolist(), color_list_from_cmap(cmap_name, len(gdf))
        )
    )

    legend_items = []
    for interval, color in color_by_label.items():
        html_string = """
        <div style="
            background-color:%s;
            width:10px; height:10px;
            display:inline-block;
            margin-right:5px;
        ">
        </div>%s
        """ % (
            color,
            interval,
        )
        legend_items.append(html_string)

    legend_html = """
    <div style="
            position: fixed;
            bottom: 50px;
            left: 50px;
            z-index:1000;
            background-color:white;
            padding: 10px;
            border: 1px solid grey;
            border-radius: 5px;
            ">
        <b>%s</b> <br> %s
    </div>
    """ % (
        title,
        "<br>".join(legend_items),
    )

    # folium_map.get_root().header.add_child(folium.Element(script + css))
    folium_map.get_root().html.add_child(folium.Element(legend_html))

    return folium_map


def plot_isochrones(
    gdf,
    poi_gdf,
    poi_name_col,
    cmap_name="viridis",
    isochrones_title="Travel time",
    add_countryborders=False,
    add_legend=False,
    custom_legend_title=None,
    add_tooltip=True,
    custom_tooltip_title=None,
):
    """
    Plot isochrones on a Folium map.

    Inputs
    ----------
    gdf (geopandas.GeoDataFrame): GeoDataFrame containing isochrone polygons.
    poi_gdf (geopandas.GeoDataFrame): GeoDataFrame containing points of
        interest.
    poi_name_col (str): Name of the column in poi_gdf to be used for labeling
        points of interest.
    cmap_name (str, optional): Name of the Matplotlib colormap to use for
        coloring the isochrones. Defaults to 'viridis'.
    isochrones_title (str, optional): Title to use for the isochrones. Defaults
        to 'Travel time'.
    add_countryborders (bool, optional): Whether or not to add a GeoJSON layer
        of country borders to the map. Defaults to False.
    add_legend (bool, optional): Whether or not to add a categorical legend to
        the map. Defaults to False.
    custom_legend_title (str, optional): Custom title to use for the legend.
        Defaults to isochrones_title.
    add_tooltip (bool, optional): Whether or not to add a tooltip to the
        isochrones. Defaults to True.
    custom_tooltip_title (str, optional): Custom title to use for the tooltip.
        Defaults to isochrones_title.

    Returns
    -------
    m (folium.Map): Folium map object containing the isochrones and points of
        interest.
    """
    # create folium map centered on the first polygon
    m = folium.Map(
        location=[
            gdf.geometry.centroid.y.mean(),
            gdf.geometry.centroid.x.mean(),
        ],
        zoom_start=10,
    )

    # add country borders as a GeoJSON layer
    if add_countryborders:
        country_borders = gpd.read_file(
            gpd.datasets.get_path("naturalearth_lowres")
        )
        folium.GeoJson(country_borders).add_to(m)

    # create dict colors
    interval_to_colour = dict(
        zip(
            gdf["interval"].tolist(), color_list_from_cmap(cmap_name, len(gdf))
        )
    )

    # add tooltip
    if add_tooltip:
        tooltip_title = isochrones_title + ":"
        if custom_tooltip_title is not None:
            tooltip_title = custom_tooltip_title
        tooltip = folium.features.GeoJsonTooltip(
            fields=["interval"], aliases=[tooltip_title], sticky=True
        )
    else:
        tooltip = None

    folium.GeoJson(
        gdf,
        style_function=lambda feature: {
            "fillColor": interval_to_colour[feature["properties"]["interval"]],
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.5,
        },
        tooltip=tooltip,
    ).add_to(m)

    m = add_pois_to_map(m, poi_gdf, poi_name_col)

    # restrict maps to boundaries geodataframe
    bounds = gdf.total_bounds
    m.fit_bounds([bounds[:2].tolist()[::-1], bounds[2:].tolist()[::-1]])

    # add legend
    if add_legend:
        legend_title = isochrones_title
        if custom_legend_title is not None:
            legend_title = custom_legend_title
        m = add_categorical_legend(
            m, title=legend_title, gdf=gdf, cmap_name=cmap_name
        )

    return m


def add_pois_to_map(m, poi_gdf, poi_name_col):
    """
    Add points of interest (POIs) to a Folium map.

    Parameters
    ----------
    m : folium.Map
        The Folium map to which the POIs will be added.
    poi_gdf : geopandas.GeoDataFrame
        The GeoDataFrame containing the POIs as point geometries.
    poi_name_col : str
        The name of the column in poi_gdf containing the names of the POIs.

    Returns
    -------
    m : folium.Map
        The Folium map with the POIs added.
    """
    for i in range(len(poi_gdf)):
        folium.Marker(
            location=[
                poi_gdf["geometry"].iloc[i].y,
                poi_gdf["geometry"].iloc[i].x,
            ],
            popup=poi_gdf[poi_name_col].iloc[i],
        ).add_to(m)
    return m


def create_input_map():
    """
    Create a Folium map with drawing tools, search bar, and minimap.

    Returns
    -------
    Map (folium.Map): Folium map object.
    """
    # Create folium map
    Map = folium.Map(
        location=[52.205276, 0.119167],
        zoom_start=3,
        control_scale=True,
        # crs='EPSG4326'
    )
    # Add drawing tools to map
    Draw(
        export=False,
        draw_options={
            "circle": False,
            "polyline": False,
            "polygon": True,
            "circle": False,
            "marker": False,
            "circlemarker": False,
        },
    ).add_to(Map)
    # Add search bar with geocoder to map
    Geocoder(add_marker=False).add_to(Map)
    # Add minimap to map
    MiniMap().add_to(Map)
    return Map


def process_poi_data(upload_poi_file):
    """Process point of interest (POI) data uploaded by the user.

    Inputs
    ----------
    upload_poi_file (FileStorage): File object containing the POI data
        uploaded by the user.

    Returns
    -------
    poi_gdf (geopandas.GeoDataFrame): GeoDataFrame containing the POI data.
    in_poi_flds (list): List of column names in the POI data.
    valid_geom (bool): True if all geometries are points, False otherwise.
    """
    poi_gdf = create_poi_gpd(upload_poi_file)
    in_poi_flds = get_poi_flds(poi_gdf)
    valid_geom = check_poi_geometry(poi_gdf)
    return poi_gdf, in_poi_flds, valid_geom


def process_aoi_data(upload_aoi_file):
    """Process area of interest (AOI) data uploaded by the user.

    Inputs
    ----------
    upload_aoi_file (FileStorage): File object containing the AOI data
        uploaded by the user.

    Returns
    -------
    aoi_gpd (geopandas.GeoDataFrame): GeoDataFrame containing the AOI data.
    valid_geom (bool): True if all geometries are polygons, False otherwise.
    """
    aoi_gpd = create_aoi_gpd(upload_aoi_file)
    valid_geom = check_aoi_geometry(aoi_gpd)
    return aoi_gpd, valid_geom

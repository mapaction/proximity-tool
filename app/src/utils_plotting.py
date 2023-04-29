"""Functions for plotting."""
from typing import List, Optional, Union

import branca
import folium
import geopandas as gpd
import matplotlib
import numpy as np
import streamlit.components.v1 as components
from folium.plugins import Draw, Geocoder, MiniMap


def color_list_from_cmap(cmap_name: str, n: int) -> Union[List[str], str]:
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


def folium_static_with_legend(
    fig,
    gdf: gpd.GeoDataFrame,
    legend_title: str,
    cmap_name: str = "viridis",
    width: int = 1800,
    height: int = 1000,
) -> None:
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


def add_categorical_legend(
    folium_map: folium.Map,
    title: str,
    gdf: gpd.GeoDataFrame,
    cmap_name: str = "viridis",
) -> folium.Map:
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
    gdf: gpd.GeoDataFrame,
    poi_gdf: gpd.GeoDataFrame,
    poi_name_col: str,
    cmap_name: str = "viridis",
    isochrones_title: str = "Travel time",
    add_countryborders: bool = False,
    add_legend: bool = False,
    custom_legend_title: Optional[str] = None,
    add_tooltip: bool = True,
    custom_tooltip_title: Optional[str] = None,
) -> folium.Map:
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
        control_scale=True,
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
    # m.fit_bounds([bounds[:2].tolist()[::-1], bounds[2:].tolist()[::-1]])

    # add legend
    if add_legend:
        legend_title = isochrones_title
        if custom_legend_title is not None:
            legend_title = custom_legend_title
        m = add_categorical_legend(
            m, title=legend_title, gdf=gdf, cmap_name=cmap_name
        )

    return m

def draw_aoi():
    # Create a map centered on a specific location
    map_center = [0, 0]  # World coordinates
    map_zoom = 2
    my_map = folium.Map(location=map_center, zoom_start=map_zoom)
    # Add a satellite basemap layer to the map
    basemap_satellite_url = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    basemap_satellite_attribution = "Esri"
    basemap_satellite_name = "ESRI Satellite"
    basemap_satellite_layer1 = folium.TileLayer(
        tiles=basemap_satellite_url,
        attr=basemap_satellite_attribution,
        name=basemap_satellite_name,
        overlay=False,
        control=True
    )
    basemap_satellite_layer1.add_to(my_map)
    # Add a satellite basemap layer with labels to the map
    basemap_satellite_url = "https://a.tile.opentopomap.org/{z}/{x}/{y}.png"
    basemap_satellite_name = "OpenTopoMap"
    basemap_satellite_attribution = "Map data: © OpenStreetMap contributors, SRTM | Map style: © OpenTopoMap"
    basemap_satellite_layer2 = folium.TileLayer(
        tiles=basemap_satellite_url,
        name=basemap_satellite_name,
        attr=basemap_satellite_attribution,
        overlay=False,
        control=True
    )
    basemap_satellite_layer2.add_to(my_map)
    
    # Add a LayerControl to the map to allow the user to toggle between the basemaps
    folium.LayerControl().add_to(my_map)
    # Add draw function to the map
    Draw(export=True).add_to(my_map)
    return my_map

def add_pois_to_map(
    m: folium.Map, poi_gdf: gpd.GeoDataFrame, poi_name_col: str
) -> folium.Map:
    """
    Add points of interest (POIs) to a Folium map.

    Parameters
    ----------
    m (folium.Map): the Folium map to which the POIs will be added.
    poi_gdf (geopandas.GeoDataFrame): the GeoDataFrame containing the POIs as
        point geometries.
    poi_name_col (str): the name of the column in poi_gdf containing the names
        of the POIs.

    Returns
    -------
    m (folium.Map): the Folium map with the POIs added.
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


def create_input_map() -> folium.Map:
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


def plot_population_summary(
    gdf: gpd.GeoDataFrame,
    figsize: tuple = (10, 6),
    cmap_name: str = "viridis",
    labelpad: int = 10,
    fontsize: int = 16,
):
    """
    Plot a horizontal bar chart of total population by travel time.

    Inputs
    ----------
    gdf (geopandas.GeoDataFrame): GeoDataFrame containing data on population
        by travel time.
    figsize (tuple, optional): size of the plot figure in inches. Defaults to
        (10, 6).
    cmap_name (str, optional): name of the colormap to use. Defaults to
        'viridis'.
    labelpad (float, optional): padding distance between axis labels and tick
        labels. Defaults to 10.
    fontsize (float, optional): font size to use for axis labels and tick
        labels. Defaults to 16.

    Returns
    -------
    fig (Figure): Matplotlib figure object containing the plot.
    """
    fig, ax = matplotlib.pyplot.subplots(figsize=figsize)

    color_list = color_list_from_cmap(cmap_name, len(gdf))

    ax.barh(gdf["interval"], gdf["total population"] / 1e6, color=color_list)
    ax.invert_yaxis()
    ax.set_title(
        "Total Population by travel time",
        pad=labelpad,
        fontsize=fontsize * 5 / 4,
    )
    ax.set_xlabel(
        "Total Population (million of people)",
        labelpad=labelpad,
        fontsize=fontsize,
    )
    ax.set_ylabel(
        "Travel time (in seconds)", labelpad=labelpad, fontsize=fontsize
    )
    ax.tick_params(axis="both", labelsize=fontsize * 3 / 4)

    return fig

"""Functions for population data."""
import geopandas as gpd
import numpy as np
import rasterio
import requests
from rasterstats import zonal_stats


def find_intersections_polygon(pol):
    """
    Find the intersections between a Polygon object and country borders.

    The country borders are retrieved from the Natural Earth dataset.

    Inputs
    ----------
    pol (shapely.Polygon): shapely Polygon object.

    Returns
    -------
    iso3_list (list): list of ISO3 country codes corresponding to the countries
        intersected by the input Polygon.
    country_intersect_list (list): list of the intersected portions of each
        country's polygon, as Polygon objects.
    """
    iso3_list = []
    country_intersect_list = []

    world_filepath = gpd.datasets.get_path("naturalearth_lowres")
    world = gpd.read_file(world_filepath)
    ind_intersect = pol.intersects(world["geometry"])
    world_intersect = world[
        world.index.isin(ind_intersect[ind_intersect].index.values)
    ]
    for i in range(len(world_intersect)):
        iso3_list.append(world_intersect["iso_a3"].iloc[i])
        country_intersect_list.append(
            world_intersect["geometry"].iloc[i].intersection(pol)
        )
    return iso3_list, country_intersect_list


def find_intersections_gdf(gdf):
    """
    Find the intersections between polygons in a dataframe and country borders.

    Inputs
    ----------
    gdf (geopandas.GeoDataFrame): GeoDataFrame containing Polygon geometries.

    Returns
    -------
    intersect_dict (dict): dictionary where the keys are the indices of the
        input GeoDataFrame and the values are dictionaries of intersected
        country polygons, keyed by ISO3 country codes.
    all_iso3_list (list): list of all ISO3 country codes intersected by any of
        the input polygons.
    """
    intersect_dict = {}
    all_iso3_list = []
    for j in range(len(gdf)):
        iso3_list, country_intersect_list = find_intersections_polygon(
            gdf["geometry"].iloc[j]
        )
        intersect_dict[j] = dict(zip(iso3_list, country_intersect_list))
        all_iso3_list += [
            iso3 for iso3 in iso3_list if iso3 not in all_iso3_list
        ]
    return intersect_dict, all_iso3_list


def find_worldpop_iso3_tif(iso3, use_local_tif=False):
    """
    Return the URL of the WorldPop population raster file for a given ISO3.

    Inputs:
    -------
    iso3 (str): ISO3 country code.
    use_local_tif (bool, optional): If True, uses a local GeoTIFF file instead
        of downloading it from the WorldPop API. Default to False.

    Returns:
    --------
    tif_url (str): URL of the GeoTIFF file containing the population density
        data for the given country. if use_local_tif is True, return the local
        path of the GeoTIFF file.
    """
    if use_local_tif:
        tif_url = f"/home/daniele/Downloads/{iso3.lower()}_ppp_2020.tif"
    else:
        api_url = f"https://www.worldpop.org/rest/data/pop/wpgp?iso3={iso3}"
        response = requests.get(api_url).json()["data"]
        tif_url = (
            "/vsicurl_streaming/"
            + [r["files"][0] for r in response if int(r["popyear"]) == 2020][0]
        )
    return tif_url


def aggregate_raster_on_geometries(raster_file, geometry_list, stats="sum"):
    """
    Compute zonal statistics of a raster file over a list of vector geometries.

    Inputs:
    -------
    raster_file (str): filepath or url to the input raster file.
    geometry_list (list): list of shapely geometries (e.g. polygons) over which
        to compute the zonal statistics.
    stats (str or list, optional): One or more statistics to compute for each
        geometry, such as 'mean', 'sum', 'min', 'max', 'std', etc. Default to
        'sum'.

    Returns:
    --------
    stats_list (list): List of zonal statistics computed for each input
        geometry, in the same order as the input list. Each item in the list is
        a dictionary containing the zonal statistics for a single geometry,
        with keys like 'sum', 'mean', etc. depending on the input 'stats'
        parameter.
    """
    raster = rasterio.open(raster_file, nodata=0.0)
    affine = raster.transform
    array = raster.read(1)
    array = array.astype(float)
    array[array < 0] = np.nan

    return zonal_stats(geometry_list, array, affine=affine, stats=stats)


def add_population_data(gdf, use_local_tif=False):
    """
    Add population data to a GeoDataFrame by aggregating WorldPop data.

    Since WorldPop population data can only be downloaded per country, the
    function calculates the intersections between the geometries in the
    dataframe and each one of the world countries. Then it calculates zonal
    statistics for each pair (geometry, country) and aggregate the results
    per geometry.

    Parameters
    ----------
    gdf (geopandas.GeoDataFram: GeoDataFrame containing the geometries for
        which to add population data.
    use_local_tif (bool, optional): whether to use local geotiff files if
        available. Default to False.

    Returns
    -------
    gdf (geopandas.GeoDataFrame): input GeoDataFrame with an additional
        'total population' column containing the aggregated population data.
    """
    pop_total_dict = {}
    intersect_dict, all_iso3_list = find_intersections_gdf(gdf)

    for i in range(len(all_iso3_list)):
        iso3 = all_iso3_list[i]
        iso3_list_indexes = [
            i for i, value in intersect_dict.items() if iso3 in value.keys()
        ]
        iso3_list_geometries = [
            value[iso3]
            for i, value in intersect_dict.items()
            if iso3 in value.keys()
        ]

        raster_file = find_worldpop_iso3_tif(iso3, use_local_tif=use_local_tif)

        pop_iso3_agg = aggregate_raster_on_geometries(
            raster_file, iso3_list_geometries
        )
        pop_partial_dict = dict(
            zip(iso3_list_indexes, [pop["sum"] for pop in pop_iso3_agg])
        )

        for key, value in pop_partial_dict.items():
            if key not in pop_total_dict:
                pop_total_dict[key] = value
            else:
                pop_total_dict[key] += value

    total_pop_list = []
    for i in gdf.index:
        total_pop_list.append(pop_total_dict[i])
    gdf["total population"] = total_pop_list

    return gdf

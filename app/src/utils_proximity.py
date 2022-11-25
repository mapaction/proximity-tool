"""Functions for proximity analysis."""
import time
from itertools import islice
from timeit import default_timer

import geopandas as gpd
import pandas as pd
from geojson.geometry import Polygon
from openrouteservice import client

params_iso = {
    "profile": "driving-car",
    "range": [900, 1800, 2700, 3600],  # 900/60 = 15 minutes,
    "range_type": "time",
    "attributes": ["total_pop"],  # Get pop count for isochrones
}

api_key = "5b3ce3597851110001cf6248f721ae98b34c4504a7d7d29fb9847568"
ors = client.Client(key=api_key)


def prep_user_poi(poi_gdata, label_col):
    """Add docstrings here."""
    start_points = {}
    poi_gdata = poi_gdata.to_crs("EPSG:4326")
    # get centroid of input POIs; used in mapping results
    map_cent = poi_gdata.dissolve().centroid
    centre_list = [map_cent.y, map_cent.x]  # reversed for folium

    label = poi_gdata[label_col]
    xcoords = poi_gdata.geometry.x
    ycoords = poi_gdata.geometry.y

    for lab, x, y in zip(label, xcoords, ycoords):
        start_points[lab] = {"location": [x, y]}
    return start_points, centre_list


# function to split start point dictionary into chunks
# called in get_isochrones function
def chunks(data, chunksize):
    """Add docstrings here."""
    it = iter(data)
    for _ in range(start=0, stop=len(data), step=chunksize):
        yield {k: data[k] for k in islice(it, chunksize)}


# make ors api calls and save results to df
def get_isochrones(start_points):
    """Add docstrings here."""
    # example of isochrone search, based on this one (initially at least):
    # https://github.com/GIScience/openrouteservice-examples/blob/master/
    # python/Apartment_Search.py
    # start timer:
    iso_start = default_timer()
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
    """Add docstrings here."""
    diss_start = default_timer()
    diss_isoc = isos.dissolve(by="value", as_index=False).reset_index()
    diss_end = default_timer()
    diss_time = diss_end - diss_start
    return diss_isoc, diss_time


# 2 Get differences (i.e. remove overlaps)
def difference_iso(diss_isoc):
    """Add docstrings here."""
    diff_start = default_timer()
    diff_isoc = gpd.GeoDataFrame(columns=["interval", "geometry"])
    diff_isoc.set_crs(epsg=4326)

    # determine interval text
    for i in range(0, len(diss_isoc)):
        # get interval text
        if i == 0:
            interval = f"0 - {int(diss_isoc.loc[i, 'value'])}"
        elif i == 6:
            interval = f"{int(diss_isoc.loc[i - 1, 'value'])} - Inf"
        else:
            v = int(diss_isoc.loc[i, "value"]) - int(diss_isoc.loc[0, "value"])
            interval = f"{v} " f"- {int(diss_isoc.loc[i, 'value'])}"

        # get difference
        if i == 0:
            diff_geom = diss_isoc.loc[i, "geometry"]
        else:
            geom_a = diss_isoc.loc[i, "geometry"]
            geom_b = diss_isoc.loc[i - 1, "geometry"]
            diff_geom = geom_a.difference(geom_b)

        # append this difference geom to dataframe
        diff_isoc = diff_isoc.append(
            {
                "interval": interval,
                "geometry": diff_geom,
            },
            ignore_index=True,
        )

        diff_isoc.crs = diss_isoc.crs

        diff_end = default_timer()
        diff_time = diff_end - diff_start

    return diff_isoc, diff_time


# 3 Fill gaps using AOI
def fill_aoi(diff_isoc, aoi):
    """Add docstrings here."""
    fill_start = default_timer()
    # get difference between aoi and final isochrones dataset
    fill_geom = aoi.difference(diff_isoc.iloc[[0]])
    for i in range(1, len(diff_isoc)):
        fill_geom = fill_geom.difference(
            diff_isoc.iloc[[i]].reset_index(drop=True)
        )
    fill_geom_gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries(fill_geom)).iloc[
        [0]
    ]
    fill_geom_gdf = fill_geom_gdf[~fill_geom_gdf.is_empty]

    # calculate the interval column to be '> the highest interval in diff_isoc'
    fill_interval = (
        "> " + diff_isoc.interval.unique()[-1:][0].rsplit("- ", 1)[1]
    )
    fill_geom_gdf["interval"] = fill_interval

    # merge difference with final isochrones dataset
    filled_to_aoi = diff_isoc.append(fill_geom_gdf).reset_index(drop=True)
    fill_end = default_timer()
    fill_time = fill_end - fill_start
    # return filled_to_aoi.reset_index(drop=True)
    return filled_to_aoi, fill_time

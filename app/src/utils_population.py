"""Functions for population data."""
import os
import urllib.request
from ftplib import FTP
from typing import Dict, List, Optional, Tuple, Union

import geopandas as gpd
import numpy as np
import rasterio
import requests
import shapely
from rasterstats import zonal_stats


def find_intersections_polygon(
    pol: shapely.Polygon,
) -> Tuple[List[str], List[shapely.Polygon]]:
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


def find_intersections_gdf(gdf: gpd.GeoDataFrame) -> Tuple[Dict, List[str]]:
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


def download_worldpop_iso_tif(
    iso3: str,
    tif_folder: str,
    method: str = "http",
    year: int = 2020,
    data_type: str = "UNadj_constrained",
    clobber: bool = False,
    use_local_tif: bool = False,
) -> str:
    """
    Download WorldPop raster data for given parameters.

    Inputs:
    -------
    iso3 (str): ISO3 country code.
    tif_folder (str): folder name, where download raster data are saved.
    method (str, optional): download method (http API or ftp service).
        ['http' | 'ftp']. Default to 'http'.
    year (int, optional): year of population data. Default to 2020.
    data_type (str, optional): type of population estimate.
        ['unconstrained'| 'constrained' | 'UNadj_constrained']. Default to
        'UNadj_constrained'.
    clobber (bool, optional): if True, overwrite data, if False do not
        download data if already present in the folder. Default to False.
    use_local_tif (bool, optional): if True, uses a local GeoTIFF file instead
        of downloading it from the WorldPop API. Default to False.

    Returns:
    --------
    filename (str): filename of the GeoTIFF file containing the population
        density data for the given parameters. if use_local_tif is True,
        return the local path of the GeoTIFF file.
    """
    allowed_method = ["http", "ftp"]
    if method not in allowed_method:
        raise ValueError(
            "method should be one of the options: " + ", ".join(allowed_method)
        )

    allowed_data_type = ["unconstrained", "constrained", "UNadj_constrained"]
    if data_type not in allowed_data_type:
        raise ValueError(
            "data_type should be one of the options: "
            + ", ".join(allowed_data_type)
        )

    filename = f"{tif_folder}/{iso3.lower()}_{year}_{data_type}.tif"

    if use_local_tif:
        return f"{tif_folder}/{iso3.lower()}_2020_UNadj_constrained.tif"

    if method == "http":
        return download_worldpop_iso3_tif_http(
            iso3,
            year=year,
            data_type=data_type,
            filename=filename,
            clobber=clobber,
        )
    else:
        return download_worldpop_iso3_tif_ftp(
            iso3,
            year=year,
            data_type=data_type,
            filename=filename,
            clobber=clobber,
        )


def download_worldpop_iso3_tif_http(
    iso3: str,
    data_type: str = "UNadj_constrained",
    filename: Optional[str] = None,
    year: int = 2020,
    clobber: bool = False,
) -> str:
    """
    Download WorldPop raster data for given parameters, using the API via http.

    Inputs:
    -------
    iso3 (str): ISO3 country code.
    data_type (str, optional): type of population estimate.
        ['unconstrained'| 'constrained' | 'UNadj_constrained']. Default to
        'UNadj_constrained'.
    filename (str, optional): filename of the downloaded raster file.
    year (int, optional): year of population data. Default to 2020.
    clobber (bool, optional): if True, overwrite data, if False do not
        download data if already present in the folder. Default to False.

    Returns:
    --------
    filename (str): filename of the GeoTIFF file containing the population
        density data for the given parameters.
    """
    if data_type == "unconstrained":
        api_suffix = "wpgp"
    elif data_type == "constrained":
        api_suffix = f"cic{year}_100m"
    else:
        api_suffix = f"cic{year}_UNadj_100m"

    api_url = (
        f"https://hub.worldpop.org/rest/data/pop/" f"{api_suffix}?iso3={iso3}"
    )

    response = requests.get(api_url)
    tif_url = response.json()["data"][0]["files"][0]

    if filename is None:
        filename = tif_url.split("/")[-1]

    if clobber:
        condition_to_download = True
    else:
        condition_to_download = not os.path.isfile(filename)

    if condition_to_download:
        urllib.request.urlretrieve(tif_url, filename)
    return filename


def download_worldpop_iso3_tif_ftp(
    iso3: str,
    data_type: str = "UNadj_constrained",
    filename: Optional[str] = None,
    year: int = 2020,
    clobber: bool = False,
) -> str:
    """
    Download WorldPop raster data for given parameters, using the ftp service.

    Inputs:
    -------
    iso3 (str): ISO3 country code.
    data_type (str, optional): type of population estimate.
        ['unconstrained'| 'constrained' | 'UNadj_constrained']. Default to
        'UNadj_constrained'.
    filename (str, optional): filename of the downloaded raster file.
    year (int, optional): year of population data. Default to 2020.
    clobber (bool, optional): if True, overwrite data, if False do not
        download data if already present in the folder. Default to False.

    Returns:
    --------
    filename (str): filename of the GeoTIFF file containing the population
        density data for the given parameters.
    """
    ftp = FTP("ftp.worldpop.org.uk")
    ftp.login()

    folder_base = "/GIS/Population/Global_2000_2020"

    if data_type == "unconstrained":
        file_suffix = ""
        folder = f"{folder_base}/{year}/{iso3}/"
    else:
        file_suffix = f"_{data_type}"
        folder_base = f"{folder_base}_Constrained/{year}/"
        ftp_sources = ["maxar_v1/", "BSGM/"]
        for source in ftp_sources:
            ftp.cwd(f"{folder_base}/{source}")
            if iso3 in ftp.nlst():
                break
        folder = f"{folder_base}/{source}{iso3}/"

    file = f"{iso3.lower()}_ppp_{year}{file_suffix}.tif"

    ftp.cwd(folder)

    if filename is None:
        filename = file

    if clobber:
        condition_to_download = True
    else:
        condition_to_download = not os.path.isfile(filename)

    if condition_to_download:
        with open(filename, "wb") as file_out:
            ftp.retrbinary(f"RETR {file}", file_out.write)

    ftp.quit()

    return filename


def aggregate_raster_on_geometries(
    raster_file: str,
    geometry_list: List[shapely.Geometry],
    stats: Union[str, List[str]] = "sum",
) -> List:
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


def add_population_data(
    gdf: gpd.GeoDataFrame,
    tif_folder: str = "app/test_data/pop_data",
    use_local_tif: bool = False,
    clobber: bool = False,
) -> gpd.GeoDataFrame:
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

    if not os.path.exists(tif_folder):
        os.makedirs(tif_folder)

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

        raster_file = download_worldpop_iso_tif(
            iso3,
            tif_folder=tif_folder,
            use_local_tif=use_local_tif,
            clobber=clobber,
        )

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

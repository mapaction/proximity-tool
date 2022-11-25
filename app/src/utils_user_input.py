"""Functions for user input."""
import geopandas as gpd


def create_poi_gpd(in_poi_file):
    """Add docstrings here."""
    in_poi_gdf = gpd.read_file(in_poi_file).head(5)
    return in_poi_gdf


# create gpd of input poi
def create_aoi_gpd(in_aoi_file):
    """Add docstrings here."""
    in_aoi_gdf = gpd.read_file(in_aoi_file)
    return in_aoi_gdf


# get field names in user uploaded POI dataset
def get_poi_flds(poi_gdf):
    """Add docstrings here."""
    # in_poi = gpd.read_file(poi_file)
    in_poi_flds = list(poi_gdf.columns)
    return in_poi_flds


# # check number of POI inside and outside of AOI
def poi_v_aoi(aoi_gdata, poi_gdata):
    """Add docstrings here."""
    aoi_sgl = aoi_gdata.geometry.unary_union  # ensure a single aoi poly
    # check for POI instances outside the AOI
    poi_within_aoi = poi_gdata[poi_gdata.geometry.within(aoi_sgl)].shape[0]
    poi_outside_aoi = poi_gdata[~poi_gdata.geometry.within(aoi_sgl)].shape[0]
    return poi_within_aoi, poi_outside_aoi

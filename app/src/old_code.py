"""Old code, possibly to be imported in the new code."""
import os

final_output_folder = "isochrones_difference_folder"

if not os.path.exists(final_output_folder):
    os.mkdir(final_output_folder)

# set final output isocrone gpkg filename
output_gpkg = "processed_iso_gpkg.gpkg"

# -----------------------------------------------------------------------------
# -------------- Print API restrictions table ---------------------------------
# -----------------------------------------------------------------------------

# TO DO: implement user defined search profile parameters with API restrictions
# limitations
# Will replace Isochrone parameter definition section above
#
# api_restrictions_dict = {'Option':['Location','Interval','Range distance',
#                                    'Range time (Foot profiles)',
#                                    'Range time (Cycling profiles)',
#                                    'Range time (Driving profiles)'],
#                          'Maximum':['5', '10', '120km', '20h', '5h', '1h']
#                          }
#
# # Create DataFrame from dict
# api_restrictions = pd.DataFrame.from_dict(api_restrictions_dict)
# # Create a section for the dataframe header
# st.header('Open Route Service API parameter restrictions')
# st.write(api_restrictions)

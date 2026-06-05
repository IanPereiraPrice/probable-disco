"""
Ensure the Python path is configured for both the maplestory_idle root
and the streamlit_app subdirectory (which uses 'from utils.data_manager import ...' style).

Import this module at the top of any router that needs it.
"""
import sys
import os

_api_dir = os.path.dirname(__file__)
_pkg_root = os.path.dirname(_api_dir)
_streamlit_app = os.path.join(_pkg_root, "streamlit_app")

for _p in (_pkg_root, _streamlit_app):
    if _p not in sys.path:
        sys.path.insert(0, _p)

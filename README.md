ibarrow-maps-generator
=====================

Download the latest radar imagery of sea ice from the Utqiaġvik region, add a
time stamp, and georeference it with GDAL to convert it into a GeoTIFF to be
used with the Avenza Maps mobile app.

Setup
-----

Install Python dependencies:

```
pip install -r requirements.txt
```

Usage
-----

Set environment variables with the working and target directories:

```
export DATA_WORKING_DIRECTORY=...
export DATA_TARGET_DIRECTORY=...
```

Then run the script:

```
./barrow.py
```

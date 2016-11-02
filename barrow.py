#!/usr/bin/python
import sys
import os
import subprocess
import logging
import urllib2
import json
import re
from datetime import datetime, timedelta
from PIL import ImageFont
from PIL import Image
from PIL import ImageDraw

workingDir = os.environ['DATA_WORKING_DIRECTORY']
targetDir = os.environ['DATA_TARGET_DIRECTORY']

logging.basicConfig(format = '%(levelname)s: %(message)s', level = logging.DEBUG)
jsonFeed = 'http://feeder.gina.alaska.edu/radar-uaf-barrow-seaice-geotif.json'

# Number of layers to process.
maxLayers = 3

# Target time interval between processed layers.
layerInterval = timedelta(minutes=30)

# How recent does the first GeoTIFF need to be?
offsetFromNow = timedelta(weeks=2)

# Acceptable time buffer before and after target time.
acceptableRange = timedelta(minutes=3)

# Download and parse GINA's Barrow sea ice GeoTIFF feed.
# The first element in the feed is the most recent GeoTIFF.
response = urllib2.urlopen(jsonFeed)
geoTiffs = json.loads(response.read())

# Create a datetime object from a date string from the GeoTIFF feed.
def dateObject(rawDate):
    # Grab the latest GeoTIFF's creation date, throwing out the time zone
    # because strptime() is not able to parse the time zone in this format.
    match = re.search('^.*(?=-0[8-9]:00$)', rawDate)
    return datetime.strptime(match.group(0), '%Y-%m-%dT%H:%M:%S')

def formatDate(dateObj):
    return dateObj.strftime('%Y-%m-%d %H:%M:%S')

# Download and save the GeoTIFF file.
def download(geoTiffUrl):
    rawGeoTiff = workingDir + '/barrow_raw.tif'
    response = urllib2.urlopen(geoTiffUrl)
    localFile = open(rawGeoTiff, 'wb')
    localFile.write(response.read())
    localFile.close()
    return rawGeoTiff

# Add time stamp to GeoTIFF and properly georeference it in EPSG:3857.
def stampGeoTiff(rawGeoTiff, dateText, index):
    finalGeoTiff = targetDir + '/barrow_sea_ice_radar_{0}.tif'.format(index)
    warpedGeoTiff = workingDir + '/warped.tif'
    plainPng = workingDir + '/plain.png'

    subprocess.call([
      'gdalwarp',
      '-s_srs',
      '+proj=aeqd +lat_0=71.2925 +lon_0=-156.788333333333 +x_0=0 +y_0=0 +a=6358944.3 +b=6358944.3 +units=m +no_defs',
      '-t_srs',
      'EPSG:3857',
      '-of',
      'GTiff',
      '-srcnodata',
      '0',
      rawGeoTiff,
      warpedGeoTiff
    ])

    subprocess.call([
      'gdal_translate',
      '-of',
      'PNG',
      warpedGeoTiff,
      plainPng
    ])

    image = Image.open(plainPng)
    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 30)
    textSize = draw.textsize(dateText, font=font)
    margin = [10, 20]
    position = [0, 0]
    position[0] = image.size[0] - textSize[0] - margin[0]
    position[1] = image.size[1] - textSize[1] - margin[1]

    draw.text(position, dateText, 255, font=font)
    draw = ImageDraw.Draw(image)
    image.save(plainPng)

    subprocess.call([
      'gdal_translate',
      '-of',
      'GTiff',
      plainPng,
      finalGeoTiff
    ])

    os.remove(rawGeoTiff)
    os.remove(warpedGeoTiff)
    os.remove(plainPng)

# Create a non-geospatial "No data for [Current Date]" placeholder image.
def createNoDataImage(dateText, index):
    noDataImage = targetDir + '/barrow_sea_ice_radar_{0}.tif'.format(index)
    text = 'No data for {0}'.format(dateText);

    imageSize = [300, 300]
    image = Image.new('L', (imageSize[0], imageSize[1]), 0)
    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 18)
    textSize = draw.textsize(text, font)
    position = [0, 0]
    position[0] = (imageSize[0] - textSize[0]) / 2
    position[1] = (imageSize[1] - textSize[1]) / 2

    draw.text((position[0], position[1]), text, 255, font=font)
    image.save(noDataImage)

# Date of the first (most recent) layer in the GeoJSON feed.
firstDate = dateObject(geoTiffs[0]['event_at'])

if(firstDate < datetime.now() - offsetFromNow):
    logging.error("Date of first GeoTIFF is not recent enough.")
    sys.exit()

# Last possible date we are interested in.
lastDate = firstDate - layerInterval * maxLayers

# Use these to strictly enforce filing of data into correct sequence position.
targetPosition = 1
success = {}

for sourcePosition in range(0, len(geoTiffs)):
    if(targetPosition > maxLayers):
        sys.exit()

    geoTiff = geoTiffs[sourcePosition]
    currentDate = dateObject(geoTiff['event_at'])

    # Compute the expected date and an acceptable time buffer on either side.
    expectedDate = firstDate - layerInterval * (targetPosition - 1)
    lowEnd = expectedDate - acceptableRange
    highEnd = expectedDate + acceptableRange

    if(currentDate > lowEnd and currentDate < highEnd):
        # Add time stamp to GeoTIFF.
        formattedDate = formatDate(currentDate)
        rawGeoTiff = download(geoTiff['source'])
        stampGeoTiff(rawGeoTiff, formattedDate, targetPosition)

        logging.info("Successfully processed layer {0} with date {1}.".format(targetPosition, formattedDate))

        # Mark this target layer as a success and move on.
        success[targetPosition] = True
        targetPosition += 1
    elif(currentDate < lowEnd and targetPosition not in success):
        formattedDate = formatDate(expectedDate)
        createNoDataImage(formattedDate, targetPosition)

        logging.error("Failed to find layer data for position {0} with expected date {1}.".format(targetPosition, formattedDate))

        # There are no more chances to find a suitable layer for this target
        # layer. Mark it as a failure and move on.
        success[targetPosition] = False
        targetPosition += 1
    elif(currentDate < lastDate):
        sys.exit()

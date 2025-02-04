import os
import json
import mysql.connector
import boto3
from chalice import Chalice

app = Chalice(app_name='backend')
app.debug = True

# s3 things
S3_BUCKET = 'kfm8nx-dp1-spotify'
s3 = boto3.client('s3')

# base URL for accessing the files
baseurl = 'http://kfm8nx-dp1-spotify.s3-website-us-east-1.amazonaws.com/'

# database things
DBHOST = os.getenv('DBHOST')
DBUSER = os.getenv('DBUSER')
DBPASS = os.getenv('DBPASS')
DB = os.getenv('DB')
db = mysql.connector.connect(user=DBUSER, host=DBHOST, password=DBPASS, database=DB)
cur = db.cursor()

# file extensions to trigger on
_SUPPORTED_EXTENSIONS = (
    '.json'
)

# ingestor lambda function
@app.on_s3_event(bucket=S3_BUCKET, events=['s3:ObjectCreated:*'])
def s3_handler(event):
  if _is_json(event.key):
    # get the file, read it, load it into JSON
    response = s3.get_object(Bucket=S3_BUCKET, Key=event.key)
    text = response["Body"].read().decode()
    data = json.loads(text)

    # parse out the data fields 1-by-1
    TITLE = data['title']
    ALBUM = data['album']
    ARTIST = data['artist']
    YEAR = data['year']
    GENRE = data['genre']

    # get the unique ID for the bundle to build the mp3 and jpg urls
    keyhead = event.key
    identifier = keyhead.split('.')
    ID = identifier[0]
    MP3 = baseurl + ID + '.mp3'
    IMG = baseurl + ID + '.jpg'

    app.log.debug("Received new song: %s, key: %s", event.bucket, event.key)

    # try to insert the song into the database
    try:
      add_song = ("INSERT INTO songs "
               "(title, album, artist, year, file, image, genre) "
               "VALUES (%s, %s, %s, %s, %s, %s, %s)")
      song_vals = (TITLE, ALBUM, ARTIST, YEAR, MP3, IMG, GENRE)
      cur.execute(add_song, song_vals)
      db.commit()

    except mysql.connector.Error as err:
      app.log.error("Failed to insert song: %s", err)
      db.rollback()

# performs suffix matching against the tuple of supported extensions
def _is_json(key):
  return key.endswith(_SUPPORTED_EXTENSIONS)



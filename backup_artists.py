from distutils.util import execute
import json
from analyzer import execute_query, execute_read_query, escape_sql_string

execute_query("DROP TABLE recs")
'''

create_artists_table = """
    CREATE TABLE IF NOT EXISTS artists (
        spotify_id VARCHAR(128) NOT NULL PRIMARY KEY,
        name TEXT NOT NULL, 
        picture TEXT DEFAULT '',
        popularity TEXT,
        votes_m INTEGER DEFAULT 0,
        votes_f INTEGER DEFAULT 0,
        votes_x INTEGER DEFAULT 0,
        votes_mix INTEGER DEFAULT 0,
        consensus TEXT DEFAULT 'UND',
        locked INTEGER DEFAULT 0
    )
"""
execute_query(create_artists_table)
# Opening JSON file
f = open('artists.json')
 
# returns JSON object as
# a dictionary
data = json.load(f)
 
# Iterating through the json
# list
for artist in data['values']:
    
    row = artist

    artist_exists = execute_read_query(f"SELECT * FROM artists WHERE spotify_id='{row[0]}'")

    if(artist_exists == None):
        query = f"INSERT INTO artists (spotify_id, name, picture, popularity, votes_m, votes_f, votes_x, votes_mix, " + \
            f"consensus, locked) VALUES ('{row[0]}', '{escape_sql_string(row[1])}', '{row[2]}', '{row[3]}', {row[4]}, {row[5]}, {row[6]}, " + \
            f"{row[7]}, '{row[8]}', '{row[9]}');"
        execute_query(query)
 
# Closing file
f.close()
'''
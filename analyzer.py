from bs4 import BeautifulSoup
import requests
import psycopg2
from psycopg2 import OperationalError
import os
import threading
import random
# import pandas as pd

connection = None
FUNDAMENTAL_GENRES = ['classical', 'country', 'edm', 'folk', 'hiphop', 'jazz', 'latin', 'rap', 'rock']

'''
Playlist analyzer class using multithreading to serve
multiple clients simultaneously.
'''
class PlaylistAnalyzer(threading.Thread):
    def __init__(self, id):
        self.progress = 0
        self.id = id
        self.result = ""
        self.playlist = None
        self.artists = {
            "male":{},
            "female":{},
            "nonbinary":{},
            "mixed_gender":{},
            "undetermined":{}
        }
        self.recs = {
            "60-100":None,
            "30-60":None,
            "0-30":None
        }
        self.num_recs = 0
        self.genres = {}
        super().__init__()
    
    def run(self): 
        CLIENT_ID = os.getenv('CLIENT_ID')
        CLIENT_SECRET = os.getenv('CLIENT_SECRET')
        AUTH_URL = 'https://accounts.spotify.com/api/token'

        # POST
        auth_response = requests.post(AUTH_URL, {
            'grant_type': 'client_credentials',
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
        })

        # convert the response to JSON
        auth_response_data = auth_response.json()

        # save the access token
        access_token = auth_response_data['access_token']

        headers = {
            'Authorization': 'Bearer {token}'.format(token=access_token)
        }

        total = 0
        underrepresented = 0

        # Request playlist information
        BASE_URL = 'https://api.spotify.com/v1/playlists/{playlist_id}'
        self.playlist = requests.get(BASE_URL.format(playlist_id=self.id), headers=headers).json()
        tracks = []
        if(self.playlist != None and 'tracks' in self.playlist):
            tracks = self.playlist['tracks']
        if('items' in tracks):
            artist_result = 'UND'

            all_artists={}

            # Start looping through all songs
            for track in tracks['items']:
                track_artists = track['track']['artists']
                for artist in track_artists:
                    total += 1
                    artist_id = artist['id']
                    if artist_id in all_artists:
                        all_artists[artist_id] += 1
                    else:
                        all_artists[artist_id] = 1
                    
            artist_ids = list(all_artists.keys())
            progress_count = 0
            while(len(artist_ids) > 0):

                # Group artists into batches of 50
                batch = artist_ids[0]
                artist_ids.pop(0)
                count = 1
                while(count < 50 and len(artist_ids) > 0):
                    batch += "," + artist_ids[0]
                    artist_ids.pop(0)
                    count += 1

                # Request information from a batch of artists
                BASE_URL='https://api.spotify.com/v1/artists?ids={batch}'
                artist_batch = requests.get(BASE_URL.format(batch=batch), headers=headers).json()
                if(artist_batch != None):
                    artist_batch = artist_batch["artists"]

                for artist_info in artist_batch:
                    genres = artist_info['genres']

                    # Keep a list of the top genres in the playlist
                    for genre in genres:
                        if(genre in self.genres):
                            self.genres[genre] += 1
                        elif(not genre in FUNDAMENTAL_GENRES):
                            self.genres[genre] = 1

                    # Analyze and classify artist
                    artist_result = "UND"
                    try:
                        artist_result = analyze(artist_info)
                    except Exception as e:
                        print(str(e))
                    artist_info['occurrences'] = all_artists[artist_info['id']]
                    if(artist_result == "F"):
                        underrepresented += artist_info['occurrences']
                        self.artists['female'][artist_info['id']] = artist_info
                    elif(artist_result == "X"):
                        underrepresented += artist_info['occurrences']
                        self.artists['nonbinary'][artist_info['id']] = artist_info
                    elif(artist_result == "M"):
                        self.artists['male'][artist_info['id']] = artist_info
                    elif(artist_result == "MIX"):
                        underrepresented += artist_info['occurrences']
                        self.artists['mixed_gender'][artist_info['id']] = artist_info
                    else:
                        self.artists['undetermined'][artist_info['id']] = artist_info

                    print("RESULT: " + artist_result)
                    progress_count += 1

                    # Update the progress of the playlist
                    self.progress = 0.95 * (progress_count / total)
            
            self.result = str(round((underrepresented / total) * 100, 1))

            # Start generating recommendations for the playlist
            rec_possible = True
            self.num_recs = 0
            exclude = list(all_artists.keys())

            # Create a sorted list of the top genres
            genres_ordered = dict(sorted(self.genres.items(), key=lambda item: item[1]))
            top_genres = list(genres_ordered.keys())[-3:]

            # Get a mainstream artist, an emerging artist, and an obscure artist
            for popularity in self.recs:
                rec = None
                if(rec_possible):

                    # Pick one of the playlist's top three genres
                    genre_start_index = random.randint(0, 2)
                    genre_index = genre_start_index

                    # Try to retrieve a recommendation related to that artist with the popularity level we want
                    # If a recommendation cannot be generated, go to the next artist
                    # And loop until we've checked all artists in the playlist
                    while(rec == None and genre_index != (genre_start_index - 1) % len(top_genres)):
                        rec = generate_rec(exclude, top_genres[genre_index], popularity)
                        genre_index = (genre_index + 1) % len(top_genres)

                    # If we couldn't get a recommendation, repeat the same process but disregard the popularity level
                    if(rec == None):
                        genre_index = genre_start_index
                        while(rec == None and genre_index != (genre_start_index - 1) % len(top_genres)):
                            rec = generate_rec(exclude, top_genres[genre_index])
                            genre_index = (genre_index + 1) % len(top_genres)

                        # If a recommendation still isn't possible, return an empty list
                        if(rec == None):
                            rec = generate_rec(exclude)

                            # At this point, note that it isn't possible to generate a recommendation from this playlist
                            # so don't bother to go through that whole process for the remaining recommendations
                            rec_possible = False

                        # Track how many recommendations it was possible to generate
                        else:
                            self.num_recs += 1
                            exclude.append(rec[0]) # Excludes duplicate recommendations
                    else:
                        self.num_recs += 1
                        exclude.append(rec[0]) # Excludes duplicate recommendations
                else:
                    rec = generate_rec(exclude)
                self.recs[popularity] = rec
            
            self.progress = 1
            
            # Go back through and update recommendations tables for underrepresented artists in this playlist
            underrepresented_artists = {**self.artists['female'], **self.artists['nonbinary']}
            for artist in underrepresented_artists:
                    update_recs_table(underrepresented_artists[artist])

        else:
            self.result = "Playlist not found"


# Determine the gender of an artist
def analyze(artist_json):

    # Query the database to check the gender of the artist
    id = artist_json['id']
    artist = artist_json['name']
    result = analyze_from_database(id)
    artist_image = ""
    if(len(artist_json['images']) > 0):
        artist_image = artist_json['images'][0]['url']
    popularity = sort_artist(artist_json)

    # If we didn't get a result, determine the artist's gender by analyzing their last.fm bio
    if(result == "UND"):
        result = analyze_from_chartmetric(artist)
    
        if(result == "UND"):
            result = analyze_via_crawl(id, artist)

        check_if_exists = execute_read_query(f"SELECT * FROM artists WHERE spotify_id='{id}'")
        query = ""

        # If we hadn't analyzed this artist before, add a new row to store their result
        if(check_if_exists == None):
            escaped_name = escape_sql_string(artist) 
            query = f"INSERT INTO artists (spotify_id, name, picture, popularity, consensus) VALUES ('{id}', " + \
                f"'{escaped_name}', '{artist_image}', '{popularity}', '{result}');"
        
        # Otherwise, update the existing row
        else:
            query = f"UPDATE artists SET consensus='{result}', picture='{artist_image}', popularity='{popularity}' WHERE spotify_id='{id}'"
        execute_query(query)
        
    # If we did get a result, make sure the image and popularity are up-to-date
    else:
        query = f"UPDATE artists SET picture='{artist_image}', popularity='{popularity}' WHERE spotify_id='{id}'"
        execute_query(query)

    return result

# Update the table of recommendations by genre
def update_recs_table(rec_artist):

        create_recs_table = f"""
            CREATE TABLE IF NOT EXISTS recs (
                artist_id TEXT NOT NULL,
                popularity TEXT NOT NULL,
                genre1 TEXT NOT NULL,
                genre2 TEXT NOT NULL,
                genre3 TEXT NOT NULL,
                genre4 TEXT NOT NULL,
                genre5 TEXT NOT NULL
            );
        """
        execute_query(create_recs_table)

        # Find the table we want to update
        artist_row = execute_read_query(f"SELECT * from recs WHERE artist_id='{rec_artist['id']}'")

        # Get a list of the artist's genres outside of the fundamental genres
        genres_list = rec_artist['genres']
        for genre in genres_list:
            genre = escape_sql_string(genre)
            if genre in FUNDAMENTAL_GENRES:
                genres_list.remove(genre)
        while(len(genres_list) < 5):
            genres_list.append('')

        # If the recommendation wasn't there before, add a new row
        if(artist_row == None):
            row = {
                "artist_id":rec_artist['id'],
                "popularity":sort_artist(rec_artist),
                "genre1": escape_sql_string(genres_list[0]),
                "genre2": escape_sql_string(genres_list[1]),
                "genre3": escape_sql_string(genres_list[2]),
                "genre4": escape_sql_string(genres_list[3]),
                "genre5": escape_sql_string(genres_list[4])
            }
            query = f"INSERT INTO recs (artist_id, popularity, genre1, genre2, genre3, genre4, genre5) VALUES " + \
                f"('{row['artist_id']}', '{row['popularity']}', '{row['genre1']}', '{row['genre2']}', '{row['genre3']}', " + \
                    f"'{row['genre4']}', '{row['genre5']}');"
            execute_query(query)
        
        # Otherwise, update the recommendation's existing row
        else:
            new_pop = sort_artist(rec_artist)
            query = f"UPDATE recs SET popularity='{new_pop}' " + \
                f"WHERE artist_id='{rec_artist['id']}'"
            execute_query(query)

# Categorize the artist's level of popularity
def sort_artist(artist):
    if(artist['popularity'] > 60):
        return '60-100'
    elif(artist['popularity'] > 30):
        return '30-60'
    else:
        return '0-30'

# Generate a recommendation based on an artist and a playlist
def generate_rec(exclude, genre=None, popularity=None):

    create_recs_table = f"""
        CREATE TABLE IF NOT EXISTS recs (
            artist_id TEXT NOT NULL,
            popularity TEXT NOT NULL,
            genre1 TEXT NOT NULL,
            genre2 TEXT NOT NULL,
            genre3 TEXT NOT NULL,
            genre4 TEXT NOT NULL,
            genre5 TEXT NOT NULL
        );
    """
    execute_query(create_recs_table)

    genre = escape_sql_string(genre)

    recs_table = None
    if(popularity == None and genre != None):
        # Retrieves a list of one-element tuples (ID of recommendation)
        recs_table = execute_read_multiple_query(f"SELECT artist_id FROM recs WHERE genre1='{genre}' OR genre2='{genre}' " + \
            f" OR genre3='{genre}' OR genre4='{genre}' OR genre5='{genre}'")
    elif(popularity != None and genre != None):
        recs_table = execute_read_multiple_query(f"SELECT artist_id FROM recs WHERE genre1='{genre}' OR genre2='{genre}' " + \
            f" OR genre3='{genre}' OR genre4='{genre}' OR genre5='{genre}' AND popularity='{popularity}'")
    else:
        recs_table = execute_read_query(f"SELECT artist_id FROM recs ORDER BY RAND() LIMIT 50")
    
    if(recs_table == None or len(recs_table) == 0):
        return None

    rec_id = random.choice(recs_table)
    rec_artist = execute_read_query(f"SELECT spotify_id, name, popularity, picture, consensus FROM artists WHERE spotify_id='{rec_id[0]}'")

    # If the recommendation is already in the playlist, or the recommendation is incorrect (category M or UND), remove it and try again
    while(len(recs_table) > 0 and rec_id[0] in exclude or (rec_artist[4] == 'M' or rec_artist[4] == 'UND')):
        recs_table.remove(rec_id)
        if (rec_artist[4] == 'M' or rec_artist[4] == "UND"):
            execute_query(f"DELETE from recs WHERE artist_id='{rec_artist[0]}'")
        if(len(recs_table) > 0):
            rec_id = random.choice(recs_table)
            rec_artist = execute_read_query(f"SELECT spotify_id, name, popularity, picture, consensus FROM artists WHERE spotify_id='{rec_id[0]}'")
    if(len(recs_table) == 0):
        return None

    return rec_artist
    
# Determine an artist's gender by crawling their last.fm bio
def analyze_via_crawl(id, artist, individual=False):

    # Get the HTML code of their last.fm page
    artist = artist.replace("/", "%2F")
    artist_page = "https://www.last.fm/music/" + artist + "/+wiki"
    page = requests.get(artist_page)
    soup = BeautifulSoup(page.content, "html.parser")

    content = soup.find(class_="wiki-content")
    no_data = soup.find(class_="no-data-message")
    
    # If no data was found, return undetermined
    if(content == None or no_data != None):
        return "UND"

    # Otherwise, grab the bio paragraph by paragraph (not to exceed 2500 characters)
    content = content.find_all("p")
    paragraph_count = 0
    bio_short = ""
    while len(bio_short) < 2500 and paragraph_count < len(content):
        bio_short += content[paragraph_count].text.lower() + " "
        paragraph_count += 1

    content = content[:paragraph_count]

    # Words that may indicate the gender of the artist
    masc_indicators = ['he', 'him', 'his', 'himself', 'frontman', 'boy']
    fem_indicators = ['she', 'her', 'hers', 'herself', 'female', 'female-fronted', 'frontwoman', 'girl']
    nonbinary_indicators = ['they', 'them', 'theirs', 'their', 'themself', 'they/them', 'non-binary', 'nonbinary']

    bio_words = bio_short.split()

    masc_count = 0
    fem_count = 0
    neutral_count = 0
    isGroup = False

    # Bands tend to have a "factbox" containing a list of their members
    # Find that factbox if it exists
    factbox = soup.find(class_="factbox")
    factbox_items = None
    members_list = None

    # If there is a factbox
    if(factbox != None):
        factbox_items = factbox.find_all(class_="factbox-item")
        for item in factbox_items:
            heading = item.find(class_="factbox-heading")
            
            # And if that factbox contains a list of members
            if(heading != None and heading.text == "Members"):

                # Then this artist is a group
                isGroup = True
                members_list = item

    # Count how many times the gendered "indicators" appear in the bio
    for indicator in masc_indicators:
        masc_count += bio_words.count(indicator)
    for indicator in fem_indicators:
        fem_count += bio_words.count(indicator)
    for indicator in nonbinary_indicators:
        neutral_count += bio_words.count(indicator)

    # If there is no factbox but the bio contains the following terms, then artist may be a group
    if("was formed" in bio_short or "formed in" in bio_short or "consists of" in bio_short or "consisting of" in bio_short):
        isGroup = True

    # If we want to "force" analyzing this artist as an individual, rather than a group,
    # override what we may have determined. (I.e. if we are calling this recursively on the members
    # of a group.)
    if(individual):
        isGroup = False

    result = "UND"

    # If the artist is a group,
    if(isGroup):

        # Analyze their tags to determine the vocalists' gender
        tags_analysis = analyze_based_on_tags(artist)

        # If this isn't succesful, recursively analyze the bios
        # of the band's individual members (if a member list was given)
        if(tags_analysis == "UND"):
            if(members_list != None):
                members = members_list.find_all("li")
                member_searches = []
                for member in members:
                    member_name = member.find("span").text
                    result = analyze_via_crawl(None, member_name, individual=True)
                    if(result != "UND"):
                        member_searches.append(result)
                
                # Determine how many genders are represented amongst the group's members
                unique = set(member_searches)
                if(len(unique) > 0):
                    if(len(unique) > 2):
                        result = "MIX"
                    else:
                        result = unique.pop()
                else:
                    result = "UND"
        else:
            result = tags_analysis

    # If the artist is an individual, use their bio/pronouns to determine their gender
    elif("frontman" in bio_short or "boy band" in bio_short or \
        (masc_count > fem_count and masc_count > neutral_count)):
        result = "M"
    elif("frontwoman" in bio_short or "female-fronted" in bio_short or "girl group" in bio_short or "all-girl" in bio_short or \
        (fem_count > masc_count and fem_count > neutral_count)):
        result = "F"
    elif(("nonbinary" in bio_short or "non-binary" in bio_short or "they/them" in bio_short) or \
        (neutral_count > masc_count and neutral_count > fem_count)):
        result = "X"
    
    # Bio takes priority over tags (especially since tags are binary in gender)
    # But if bio analysis wasn't successful, check the tags
    else:
        result = analyze_based_on_tags(artist)

    # if(id != None):


    return result

# Determine the artist's gender based on tags
def analyze_based_on_tags(artist):
    
    # Get the HTML code of their last.fm page
    artist_page = "https://www.last.fm/music/" + artist + "/+tags"
    page = requests.get(artist_page)
    soup = BeautifulSoup(page.content, "html.parser")

    # Find their tags
    tags = soup.find_all(class_="big-tags-item")
    for tag in tags:
        tag_name = tag.find(class_="link-block-target").text

        # If the artist is tagged with their gender, return that result
        if(tag_name.lower() == "female vocalists" or tag_name.lower() == "girl group"):
            return "F"
        elif(tag_name.lower() == "male vocalists" or tag_name.lower() == "boy band"):
            return "M"
    
    return "UND"

# Determine an artist's gender based on what we've recorded in our database
def analyze_from_database(id):

    # execute_query("DROP TABLE artists")
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
    result = execute_read_query(f"SELECT consensus FROM artists WHERE spotify_id='{id}'")
    if(result == None):
        return "UND"
    else:
        return result[0]

def analyze_from_chartmetric(name):
    escaped_name = escape_sql_string(name)
    result = execute_read_query(f"SELECT result FROM chartmetric WHERE name='{escaped_name}'")
    if(result == None):
        return "UND"
    else:
        execute_query(f"DELETE from chartmetric WHERE name='{escaped_name}'")
        return result[0]

def cast_vote(artist_id, category):
    category_to_update = "votes_" + category.lower()
    query = f"UPDATE artists SET {category_to_update} = {category_to_update} + 1 WHERE spotify_id='{artist_id}'"
    execute_query(query)

# Update artist category after fact-checking
def update_result(artists_list, updates_json):
    for category in artists_list:
        artists_popped = []
        for id in artists_list[category]:
            if id in updates_json:
                if 'category' in updates_json[id]:
                    if(updates_json[id]['category'] == 'M'):
                        artists_list['male'][id] = artists_list[category][id]   
                        cast_vote(id, 'M')
                        artists_popped.append(id)
                    elif(updates_json[id]['category'] == 'F'):
                        artists_list['female'][id] = artists_list[category][id]   
                        cast_vote(id, 'F')
                        artists_popped.append(id)
                    elif(updates_json[id]['category'] == 'X'):
                        artists_list['nonbinary'][id] = artists_list[category][id]   
                        cast_vote(id, 'X')
                        artists_popped.append(id)
                    elif(updates_json[id]['category'] == 'MIX'):
                        artists_list['mixed_gender'][id] = artists_list[category][id]   
                        cast_vote(id, 'MIX')
                        artists_popped.append(id)

        # Remove all artists from their old categories as displayed
        for id in artists_popped:
            artists_list[category].pop(id)
    return artists_list

def get_unlocked(artists_list):
    artists_unlocked = artists_list
    for category in artists_list:
        for id in category:
            locked = execute_read_query(f"SELECT locked FROM artists WHERE spotify_id='{id}'")
            if(locked == 1):
                artists_unlocked[category].pop(id)
    return artists_unlocked

def escape_sql_string(string):
    if(string != None):
        return string.replace('\0', '\\0').replace('\'', '\'\'').replace('\"', '\"\"').replace('\b', '\\b') \
            .replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t').replace('\Z', '\\Z').replace('\\', '\\\\') \
            .replace('%', '\%').replace('_', '\_')
    else:
        return ""

# Execute SQL query
def execute_query(query):
    global connection
    if(connection == None):
        # connection = psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')
        connection = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database="postgres",
            user="postgres",
            password=os.getenv('DB_PASSWORD'))
        connection.autocommit = True
    cursor = connection.cursor()
    try:
        cursor.execute(query)
    except OperationalError as e:
        print(f"The error '{e}' occurred")

# Read single row from SQL table
def execute_read_query(query):
    global connection
    if(connection == None):
        connection = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database="postgres",
            user="postgres",
            password=os.getenv('DB_PASSWORD'))
        connection.autocommit = True
    cursor = connection.cursor()
    result = None
    try:
        cursor.execute(query)
        result = cursor.fetchone()
        return result
    except OperationalError as e:
        print(f"The error '{e}' occurred")

# Read multiple rows from SQL table
def execute_read_multiple_query(query):
    global connection
    if(connection == None):
        connection = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database="postgres",
            user="postgres",
            password=os.getenv('DB_PASSWORD'))
        connection.autocommit = True
    cursor = connection.cursor()
    result = None
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except OperationalError as e:
        print(f"The error '{e}' occurred")
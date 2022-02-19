from bs4 import BeautifulSoup
import requests
import psycopg2
from psycopg2 import OperationalError
import os
import threading
import random

connection = None

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
        self.top_artists = []
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
        artists_checked = {}

        BASE_URL = 'https://api.spotify.com/v1/playlists/{playlist_id}'
        self.playlist = requests.get(BASE_URL.format(playlist_id=self.id), headers=headers).json()

        tracks = self.playlist['tracks']
        if('items' in tracks):
            total_tracks = len(tracks['items'])
            current_track = 0
            artist_result = 'UND'

            # Start looping through all songs
            for track in tracks['items']:
                track_artists = track['track']['artists']
                for artist in track_artists:
                    total += 1
                    artist_info = requests.get(artist['href'], headers=headers).json()
                    artist_id = artist_info['id']
                    print(artist_info['name'])

                    # Track how many times the artist appears in this playlist
                    occurrences = 1

                    # If we have already checked this artist, retrieve the result we've stored for them
                    if(artist_id in artists_checked):
                        artist_result = artists_checked[artist_id]
                        if(artist_result == "F" or artist_result == "X"):
                            underrepresented += 1
                            occurrences = self.artists['female'][artist_id]['occurrences'] + 1
                            self.artists['female'][artist_id]['occurrences'] = occurrences
                        elif(artist_result == "X"):
                            underrepresented += 1
                            occurrences = self.artists['nonbinary'][artist_id]['occurrences'] + 1
                            self.artists['nonbinary'][artist_id]['occurrences'] = occurrences
                        elif(artist_result == "M"):
                            occurrences = self.artists['male'][artist_id]['occurrences'] + 1
                            self.artists['male'][artist_id]['occurrences'] = occurrences
                        elif(artist_result == "MIX"):
                            occurrences = self.artists['mixed_gender'][artist_id]['occurrences'] + 1
                            self.artists['mixed_gender'][artist_id]['occurrences'] = occurrences
                        else:
                            occurrences = self.artists['undetermined'][artist_id]['occurrences'] + 1
                            self.artists['undetermined'][artist_id]['occurrences'] = occurrences
                    else:

                        # If not, analyze the artist and store the result in case the artist
                        # appears later on the same playlist
                        artist_result = analyze(artist_info)
                        artist_info['occurrences'] = 1
                        if(artist_result == "F" or artist_result == "X"):
                            underrepresented += 1
                            self.artists['female'][artist['id']] = artist_info
                        elif(artist_result == "X"):
                            underrepresented += 1
                            self.artists['nonbinary'][artist['id']] = artist_info
                        elif(artist_result == "M"):
                            self.artists['male'][artist['id']] = artist_info
                        elif(artist_result == "MIX"):
                            self.artists['mixed_gender'][artist['id']] = artist_info
                        else:
                            self.artists['undetermined'][artist['id']] = artist_info
                        artists_checked[artist_id] = artist_result

                    # Keep a list of all artists ordered by number of occurances in the playlist
                    if(len(self.top_artists) == 0):
                        self.top_artists.append(artist_info)
                    else:

                        # TODO: This is an insertion sort - inefficient! Change to binary sort
                        index = len(self.top_artists) - 1 
                        while(self.top_artists[index]['id'] != artist_info['id'] and \
                            self.top_artists[index]['occurrences'] < occurrences and index > 0):
                            index -= 1
                        if(self.top_artists[index]['id'] == artist_info['id']):
                            self.top_artists[index]['occurrences'] = occurrences
                        else:
                            self.top_artists.insert(index, {'id':artist_info['id'], 'occurrences':occurrences})
                    print("RESULT: " + artist_result)
                    print()
                current_track += 1

                # Update the progress of the playlist
                self.progress = 0.95 * (current_track / total_tracks)
            
            self.result = str(round((underrepresented / total) * 100, 1))

            # Start generating recommendations for the playlist
            rec_possible = True
            self.num_recs = 0
            exclude = list(artists_checked.keys())

            # Get a mainstream artist, an emerging artist, and an obscure artist
            for popularity in self.recs:
                rec = None
                if(rec_possible):

                    # Pick one of the playlist's top three artists
                    artist_start_index = random.randint(0, 3)
                    artist_index = artist_start_index

                    # Try to retrieve a recommendation related to that artist with the popularity level we want
                    # If a recommendation cannot be generated, go to the next artist
                    # And loop until we've checked all artists in the playlist
                    while(rec == None and artist_index != (artist_start_index - 1) % len(self.top_artists)):
                        rec = generate_rec(self.top_artists[artist_index]['id'], exclude, popularity)
                        artist_index = (artist_index + 1) % len(self.top_artists)

                    # If we couldn't get a recommendation, repeat the same process but disregard the popularity level
                    if(rec == None):
                        artist_start_index = random.randint(0, 3)
                        artist_index = artist_start_index
                        while(rec == None and artist_index != (artist_start_index - 1) % len(self.top_artists)):
                            rec = generate_rec(self.top_artists[artist_index]['id'], exclude)
                            artist_index = (artist_index + 1) % len(self.top_artists)

                        # If a recommendation still isn't possible, return an empty list
                        if(rec == None):
                            print("Rec not possible")
                            rec = ["", "", "", "", 0]

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
                    rec = ["", "", "", "", 0]
                self.recs[popularity] = rec
            
            self.progress = 1

            # Go back through and update recommendations tables for artists in this playlist
            underrepresented_artists = {**self.artists['female'], **self.artists['nonbinary']}
            for category in self.artists:
                for outer_artist in self.artists[category]:
                    for inner_artist in underrepresented_artists:
                        if(outer_artist == inner_artist):
                            pass
                        else:
                            update_recs_table(self.artists[category][outer_artist], underrepresented_artists[inner_artist])

        else:
            self.result = "Playlist not found"


# Determine the gender of an artist
def analyze(artist_json):

    # Connect to the SQL database
    global connection
    connection = psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')
    connection.autocommit = True

    # Query that database to check the gender of the artist
    id = artist_json['id']
    artist = artist_json['name']
    result = analyze_from_database(id)
    artist_image = ""
    if(len(artist_json['images']) > 0):
        artist_image = artist_json['images'][0]['url']
    popularity = sort_artist(artist_json)


    # If we didn't get a result, determine the artist's gender by analyzing their last.fm bio
    if(result == "UND"):
        result = analyze_via_crawl(id, artist)

        check_if_exists = execute_read_query(f"SELECT * FROM artists WHERE spotify_id='{id}'")
        query = ""

        # If we hadn't analyzed this artist before, add a new row to store their result
        if(check_if_exists == None):
            escaped_name = artist.replace('\0', '\\0').replace('\'', '\'\'').replace('\"', '\"\"').replace('\b', '\\b') \
            .replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t').replace('\Z', '\\Z').replace('\\', '\\\\') \
                .replace('%', '\%').replace('_', '\_')
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

    create_recs_table = f"""
        CREATE TABLE IF NOT EXISTS recs (
            source_id TEXT NOT NULL,
            rec_id TEXT NOT NULL,
            matches INT NOT NULL
        )
    """
    execute_query(create_recs_table)
    return result

# Update an artist's table of associated/similar acts to generate recommendations later
def update_recs_table(source_artist, rec_artist):

    # Find the table we want to update
    artist_row = execute_read_query(f"SELECT * from recs WHERE source_id='{source_artist['id']}' AND rec_id='{rec_artist['id']}'")

    # If the recommendation wasn't there before, add a new row
    if(artist_row == None):
        row = {
            "source_id":source_artist['id'],
            "rec_id":rec_artist['id'],
            "matches":rec_artist['occurrences']
        }
        query = f"INSERT INTO recs (source_id, rec_id, matches) VALUES " + \
            f"('{row['source_id']}', '{row['rec_id']}', {row['matches']});"
        execute_query(query)
    
    # Otherwise, update the recommendation's existing row
    else:
        new_matches = rec_artist['occurrences'] + artist_row[2]
        query = f"UPDATE recs SET matches={new_matches} " + \
            f"WHERE source_id='{source_artist['id']}' AND rec_id='{rec_artist['id']}'"
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
def generate_rec(id, exclude, popularity=None):

    # Retrieves a list of one-element tuples (ID of recommendation)
    recs_table = execute_read_multiple_query(f"SELECT rec_id FROM recs WHERE source_id='{id}' ORDER BY matches DESC")
    # print("RECS TABLE:  " + str(recs_table))
    
    if(recs_table == None or len(recs_table) == 0):
        return None

    for rec in recs_table:
        rec_id = rec[0]
        if(not(rec_id in exclude)): # If the recommendation is not already in the playlist
            rec_artist = execute_read_query(f"SELECT spotify_id, name, popularity, picture FROM artists WHERE spotify_id='{rec_id}'")
            if(popularity != None and rec_artist[2] == popularity):
                return rec_artist
            elif(popularity == None):
                return rec_artist
    return None

    
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
            picture TEXT,
            popularity TEXT,
            votes_m INTEGER,
            votes_f INTEGER,
            votes_x INTEGER,
            votes_mix INTEGER,
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

# Execute SQL query
def execute_query(query):
    global connection
    if(connection == None):
        connection = psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')
        connection.autocommit = True
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
        connection = psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')
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
        connection = psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')
        connection.autocommit = True
    cursor = connection.cursor()
    result = None
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except OperationalError as e:
        print(f"The error '{e}' occurred")
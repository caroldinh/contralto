from bs4 import BeautifulSoup
import requests
import psycopg2
from psycopg2 import OperationalError
import os
import random
import json

connection = None

def analyze(artist_json):
    global connection
    connection = psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')
    connection.autocommit = True
    id = artist_json['id']
    artist = artist_json['name']
    result = analyze_from_database(id)
    if(result == "UND"):
        result = analyze_via_crawl(id, artist)
    create_recs_table = f"""
        CREATE TABLE IF NOT EXISTS recs{id} (
            spotify_id VARCHAR(128) NOT NULL PRIMARY KEY,
            name TEXT NOT NULL, 
            popularity TEXT NOT NULL,
            picture TEXT,
            matches INT NOT NULL
        )
    """
    '''
    try:
        execute_query(f"DROP TABLE {id}")
    except:
        pass
    '''
    execute_query(create_recs_table)
    return result

def update_recs_table(table_artist, add_artist):
    artist_row = execute_read_query(f"SELECT * from recs{table_artist['id']} WHERE spotify_id='{add_artist['id']}'")
    artist_image = None
    if(len(add_artist['images']) > 0):
        artist_image = add_artist['images'][0]['url']
    escaped_name = add_artist['name'].replace('\0', '\\0').replace('\'', '\'\'').replace('\"', '\"\"').replace('\b', '\\b').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t').replace('\Z', '\\Z').replace('\\', '\\\\').replace('%', '\%').replace('_', '\_')
    artist = {
        "spotify_id":add_artist['id'],
        "name":escaped_name,
        "popularity":sort_artist(add_artist),
        "picture":artist_image,
        "matches":add_artist['occurrences']
    }
    if(artist_row == None):
        query = f"INSERT INTO recs{table_artist['id']} (spotify_id, name, popularity, picture, matches) VALUES " + \
            f"('{artist['spotify_id']}', '{artist['name']}', '{artist['popularity']}', '{artist['picture']}', {artist['matches']});"
        execute_query(query)
    else:
        new_matches = add_artist['occurrences'] + artist_row[4]
        query = f"UPDATE recs{table_artist['id']} SET popularity='{artist['popularity']}', picture='{artist['picture']}', matches={new_matches} " + \
            f"WHERE spotify_id='{artist['spotify_id']}'"
        execute_query(query)
    artist_row = None

def sort_artist(artist):
    if(artist['popularity'] > 60):
        return '60-100'
    elif(artist['popularity'] > 30):
        return '30-60'
    else:
        return '0-30'

def generate_rec(id, popularity=None):
    global connection
    connection = psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')
    connection.autocommit = True
    recs_table = None
    if(popularity == None):
        recs_table = execute_read_multiple_query(f"SELECT * FROM recs{id}")
    else:
        recs_table = execute_read_multiple_query(f"SELECT * FROM recs{id} WHERE popularity='{popularity}'")
    if(recs_table == None):
        return None
    return str(random.choice(recs_table))

def analyze_via_crawl(id, artist, individual=False):

    artist = artist.replace("/", "%2F")

    artist_page = "https://www.last.fm/music/" + artist + "/+wiki"
    page = requests.get(artist_page)
    soup = BeautifulSoup(page.content, "html.parser")

    content = soup.find(class_="wiki-content")
    no_data = soup.find(class_="no-data-message")
    
    if(content == None or no_data != None):
        return "UND"
    content = content.find_all("p")
    paragraph_count = 0
    bio_short = ""
    while len(bio_short) < 2500 and paragraph_count < len(content):
        bio_short += content[paragraph_count].text.lower() + " "
        paragraph_count += 1

    content = content[:paragraph_count]

    masc_indicators = ['he', 'him', 'his', 'himself', 'frontman', 'boy']
    fem_indicators = ['she', 'her', 'hers', 'herself', 'female', 'female-fronted', 'frontwoman', 'girl']
    nonbinary_indicators = ['they', 'them', 'theirs', 'their', 'themself', 'they/them', 'non-binary', 'nonbinary']

    bio_words = bio_short.split()

    masc_count = 0
    fem_count = 0
    neutral_count = 0
    isGroup = False

    factbox = soup.find(class_="factbox")
    factbox_items = None
    members_list = None
    if(factbox != None):
        factbox_items = factbox.find_all(class_="factbox-item")
        for item in factbox_items:
            heading = item.find(class_="factbox-heading")
            if(heading != None and heading.text == "Members"):
                isGroup = True
                members_list = item

    for indicator in masc_indicators:
        masc_count += bio_words.count(indicator)

    for indicator in fem_indicators:
        fem_count += bio_words.count(indicator)

    for indicator in nonbinary_indicators:
        neutral_count += bio_words.count(indicator)

    if("was formed" in bio_short or "formed in" in bio_short or "consists of" in bio_short or "consisting of" in bio_short):
        isGroup = True

    if(individual):
        isGroup = False

    result = "UND"

    if(isGroup):
        tags_analysis = analyze_based_on_tags(artist)
        if(tags_analysis == "UND"):
            if(members_list != None):
                members = members_list.find_all("li")
                member_searches = []
                for member in members:
                    member_name = member.find("span").text
                    result = analyze_via_crawl(None, member_name, individual=True)
                    if(result != "UND"):
                        member_searches.append(result)
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

    elif("frontman" in bio_short or "boy band" in bio_short or \
        (masc_count > fem_count and masc_count > neutral_count)):
        result = "M"
    
    elif("frontwoman" in bio_short or "female-fronted" in bio_short or "girl group" in bio_short or "all-girl" in bio_short or \
        (fem_count > masc_count and fem_count > neutral_count)):
        result = "F"

    # This line basically indicates that they are non-binary/gnc
    elif(("nonbinary" in bio_short or "non-binary" in bio_short or "they/them" in bio_short) or \
        (neutral_count > masc_count and neutral_count > fem_count)):
        result = "X"
    
    else:
        result = analyze_based_on_tags(artist)

    if(id != None):
        check_if_exists = execute_read_query(f"SELECT * FROM artists WHERE spotify_id='{id}'")
        query = ""
        if(check_if_exists == None):
            escaped_name = artist.replace('\0', '\\0').replace('\'', '\'\'').replace('\"', '\"\"').replace('\b', '\\b').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t').replace('\Z', '\\Z').replace('\\', '\\\\').replace('%', '\%').replace('_', '\_')
            query = f"INSERT INTO artists (spotify_id, name, consensus) VALUES ('{id}', '{escaped_name}', '{result}');"
        else:
            query = f"UPDATE artists SET consensus='{result}' WHERE spotify_id='{id}'"
        print(query)
        execute_query(query)
    return result

def analyze_based_on_tags(artist):
    
    artist_page = "https://www.last.fm/music/" + artist + "/+tags"
    page = requests.get(artist_page)
    soup = BeautifulSoup(page.content, "html.parser")

    tags = soup.find_all(class_="big-tags-item")
    for tag in tags:
        tag_name = tag.find(class_="link-block-target").text
        if(tag_name.lower() == "female vocalists" or tag_name.lower() == "girl group"):
            return "F"
        elif(tag_name.lower() == "male vocalists" or tag_name.lower() == "boy band"):
            return "M"
    
    return "UND"

def analyze_from_database(id):

    # execute_query("DROP TABLE artists")

    create_artists_table = """
        CREATE TABLE IF NOT EXISTS artists (
            spotify_id VARCHAR(128) NOT NULL PRIMARY KEY,
            name TEXT NOT NULL, 
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

def execute_query(query):
    global connection
    connection.autocommit = True
    cursor = connection.cursor()
    try:
        cursor.execute(query)
    except OperationalError as e:
        print(f"The error '{e}' occurred")

def execute_read_query(query):
    global connection
    cursor = connection.cursor()
    result = None
    try:
        cursor.execute(query)
        result = cursor.fetchone()
        return result
    except OperationalError as e:
        print(f"The error '{e}' occurred")

def execute_read_multiple_query(query):
    global connection
    cursor = connection.cursor()
    result = None
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except OperationalError as e:
        print(f"The error '{e}' occurred")

# print(analyze_from_database("6olE6TJLqED3rqDCT0FyPh"))
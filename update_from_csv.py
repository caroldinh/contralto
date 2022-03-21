from analyzer import execute_query, execute_read_multiple_query, execute_read_query, escape_sql_string, update_recs_table, sort_artist
import csv
import requests
import os
import unidecode

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


with open('chartmetric.csv', 'r') as file:
    reader = csv.reader(file)
    total_count = 611617
    count = 0

    # Look at every row in the CSV
    for row in reader:
        result = "UND"
        if(row[5] == "FALSE"):
            if(row[3] == 'she/her' or row[4] == 'female'):
                result = "F"
            elif(row[3] == 'he/him' or row[4] == 'male'):
                result = "M"
            else:
                result = "X"
        elif(row[5] == "TRUE"):
            if(row[4] == 'female'):
                result = "F"
            elif(row[4] == 'male'):
                result = "M"
            elif(row[4] == 'mixed'):
                result = "MIX"

        # If a result is possible,
        if(result != "UND"):
            try: 
                artist_name = unaccented_string = unidecode.unidecode(row[1])
                BASE_URL = 'https://api.spotify.com/v1/search?q={artist_name}&type=artist&limit=1&offset=0'
                artist_request = requests.get(BASE_URL.format(artist_name=artist_name), headers=headers).json()
                artist = None

                # And that artist is in the database,
                if(artist_request["artists"]["total"] != 0):
                    artist = artist_request["artists"]["items"][0]
                    id = artist["id"]
                    genres = artist["genres"]
                    artist_image = ""
                    if(len(artist['images']) > 0):
                        artist_image = artist['images'][0]['url']
                    popularity = sort_artist(artist)

                    check_if_exists = execute_read_query(f"SELECT * FROM artists WHERE spotify_id='{id}'")
                    query = ""

                    # If we hadn't analyzed this artist before, add a new row to store their result
                    if(check_if_exists == None):
                        escaped_name = escape_sql_string(artist_name) 
                        query = f"INSERT INTO artists (spotify_id, name, picture, popularity, consensus, locked) VALUES ('{id}', " + \
                            f"'{escaped_name}', '{artist_image}', '{popularity}', '{result}', 1);"
                    
                    # Otherwise, update the existing row
                    else:
                        query = f"UPDATE artists SET consensus='{result}', picture='{artist_image}', popularity='{popularity}', locked=1 WHERE spotify_id='{id}'"
                    execute_query(query)

                    if(result == "F" or result == "X"):
                        update_recs_table(artist)
            except:
                print("Error")
        count += 1
        print(str(count) + " / " + str(total_count))


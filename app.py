from flask import Flask, request, render_template, redirect, url_for
from analyzer import analyze, update_recs_table, generate_rec
import requests
import sys
import threading
import os
import logging
import random

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
            "male_led":{},
            "underrepresented":{},
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
                            occurrences = self.artists['underrepresented'][artist_id]['occurrences'] + 1
                            self.artists['underrepresented'][artist_id]['occurrences'] = occurrences
                        elif(artist_result == "M"):
                            occurrences = self.artists['male_led'][artist_id]['occurrences'] + 1
                            self.artists['male_led'][artist_id]['occurrences'] = occurrences
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
                            self.artists['underrepresented'][artist['id']] = artist_info
                        elif(artist_result == "M"):
                            self.artists['male_led'][artist['id']] = artist_info
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
                        rec = generate_rec(self.top_artists[artist_index]['id'], artists_checked.keys(), popularity)
                        artist_index = (artist_index + 1) % len(self.top_artists)

                    # If we couldn't get a recommendation, repeat the same process but disregard the popularity level
                    if(rec == None):
                        artist_start_index = random.randint(0, 3)
                        artist_index = artist_start_index
                        while(rec == None and artist_index != (artist_start_index - 1) % len(self.top_artists)):
                            rec = generate_rec(self.top_artists[artist_index]['id'], artists_checked.keys())
                            artist_index = (artist_index + 1) % len(self.top_artists)

                        # If a recommendation still isn't possible, return an empty list
                        if(rec == None):
                            rec = ["", "", "", "", 0]

                            # At this point, note that it isn't possible to generate a recommendation from this playlist
                            # so don't bother to go through that whole process for the remaining recommendations
                            rec_possible = False

                        # Track how many recommendations it was possible to generate
                        else:
                            self.num_recs += 1
                    else:
                        self.num_recs += 1
                else:
                    rec = ["", "", "", "", 0]
                self.recs[popularity] = rec
            
            self.progress = 1

            # Go back through and update recommendations tables for artists in this playlist
            for category in self.artists:
                for outer_artist in self.artists[category]:
                    for inner_artist in self.artists['underrepresented']:
                        if(outer_artist == inner_artist):
                            pass
                        else:
                            update_recs_table(self.artists[category][outer_artist], self.artists['underrepresented'][inner_artist])

        else:
            self.result = "Playlist not found"

app = Flask(__name__)
app.debug = True
log = logging.getLogger('werkzeug')
log.disabled = True

analyzers = {}

@app.route("/", methods=['GET'])
def index():
    print("started")
    return render_template('index.html')

@app.route('/', methods=['POST'])
def submit_link():
    print("Clicked", file=sys.stdout)
    url = request.form['playlist-url']
    print(url, file=sys.stderr)
    if url.startswith('open.spotify.com/playlist/') \
        or url.startswith('https://open.spotify.com/playlist/') \
        or url.startswith('http://open.spotify.com/playlist/'):
            start_index = url.index('open.spotify.com/playlist/') + len('open.spotify.com/playlist/')
            end_index = url.index('?si=')
            id = url[start_index:end_index]
            return redirect(id)
    else:
        return render_template('index.html', error_msg="Your playlist must be a Spotify playlist link.")

@app.route('/<playlist_id>')
def analyze_playlist(playlist_id):
    analyzers[playlist_id] = PlaylistAnalyzer(playlist_id)
    analyzers[playlist_id].start()
    return render_template('loading.html', id=playlist_id)

@app.route('/analyzer-progress/<playlist_id>')
def get_progress(playlist_id):
    global analyzer
    return str(analyzers[playlist_id].progress)

@app.route('/analyzer-result/<playlist_id>')
def get_analyzer_result(playlist_id):
    global analyzer
    if(playlist_id in analyzers):
        return analyzers[playlist_id].result

@app.route('/<playlist_id>/info/')
def get_playlist_info(playlist_id):
    global analyzers
    if(playlist_id in analyzers):
        return analyzers[playlist_id].playlist

@app.route('/<playlist_id>/result/')
def display_result(playlist_id):
    global analyzers
    if(playlist_id in analyzers):
        result = analyzers[playlist_id].result
        # analyzers[playlist_id] = None
        return render_template('results.html', id=playlist_id, result=result, playlist=analyzers[playlist_id].playlist, \
            recs=analyzers[playlist_id].recs, num_recs=analyzers[playlist_id].num_recs)
    else:
        return redirect(url_for('analyze_playlist', playlist_id=playlist_id))

@app.route('/<playlist_id>/artists/')
def get_artists(playlist_id):
    global analyzers
    if(playlist_id in analyzers):
        return analyzers[playlist_id].artists
    else:
        return ""

@app.route('/<artist_id>/recs-table/')
def generate_recs_table(artist_id):
    return generate_rec(artist_id)

if __name__ == '__main__':
    app.run(threaded=True)
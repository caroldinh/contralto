from flask import Flask, request, render_template, redirect, url_for
from analyzer import analyze, update_recs_table, generate_rec
import requests
import sys
import threading
import os
import logging
import psycopg2
from psycopg2 import OperationalError
import random

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
                    occurrences = 1
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
                    if(len(self.top_artists) == 0):
                        self.top_artists.append(artist_info)
                    else:
                        index = len(self.top_artists) - 1 
                        while(self.top_artists[index]['id'] != artist_info['id'] and \
                            self.top_artists[index]['occurrences'] < occurrences and index > 0):
                            index -= 1
                        if(self.top_artists[index]['id'] == artist_info['id']):
                            self.top_artists[index]['occurrences'] = occurrences
                        elif(index < len(self.top_artists) - 1):
                            self.top_artists.insert(index, artist_info)
                        if(len(self.top_artists) > 5):
                            self.top_artists.pop()
                    print("RESULT: " + artist_result)
                    print()
                current_track += 1
                self.progress = current_track / total_tracks
            
            self.result = str(round((underrepresented / total) * 100, 1))
            # Go back through and update recommendations tables for artists in this playlist
            for category in self.artists:
                for outer_artist in self.artists[category]:
                    for inner_artist in self.artists['underrepresented']:
                        if(outer_artist == inner_artist):
                            pass
                        else:
                            update_recs_table(self.artists[category][outer_artist], self.artists['underrepresented'][inner_artist])
                    print()

            print()
            rec_artists = []
            for x in range(3):
                rec_artist = random.choice(self.top_artists)
                if(len(self.top_artists) > 3):
                    self.top_artists.remove(rec_artist)
            count = 0
            for popularity in self.recs:
                if(len(rec_artists) > count):
                    self.recs[popularity] = generate_rec(rec_artists[count]['id'], popularity)
                    if(self.recs[popularity] == None):
                        self.recs[popularity] = generate_rec(rec_artists[count]['id'])
            
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
        return render_template('results.html', id=playlist_id, result=result, playlist=analyzers[playlist_id].playlist)
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
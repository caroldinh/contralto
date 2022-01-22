from flask import Flask, request, render_template, redirect, url_for
from bio_analyzer import analyze
import requests
import sys
import threading
import os

class PlaylistAnalyzer(threading.Thread):
    def __init__(self, id):
        self.progress = 0
        self.id = id
        self.result = ""
        super().__init__()
    
    def run(self): 
        CLIENT_ID = os.environ['CLIENT_ID']
        CLIENT_SECRET = os.environ['CLIENT_SECRET']
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

        BASE_URL = "https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        tracks = requests.get(BASE_URL.format(playlist_id=self.id), headers=headers).json()
        if('items' in tracks):
            total_tracks = len(tracks['items'])
            current_track = 0
            for track in tracks['items']:
                track_artists = track['track']['artists']
                for artist in track_artists:
                    total += 1
                    artist_name = artist['name']
                    print(artist_name)
                    if(artist_name in artists_checked):
                        result = artists_checked[artist_name]
                    else:
                        result = analyze(artist_name)
                        artists_checked[artist_name] = result
                    print(result)
                    print()
                    if(result == "Female or female-fronted" or result == "Nonbinary or nonbinary-fronted"):
                        underrepresented += 1
                current_track += 1
                self.progress = current_track / total_tracks

            print()
            self.result = str((underrepresented / total) * 100) + " percent of this playlist is led by a female or nonbinary artist."

        else:
            self.result = "Playlist not found"


app = Flask(__name__)
app.debug = True

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
    global analyzers
    start_index = url.index('open.spotify.com/playlist/') + len('open.spotify.com/playlist/')
    end_index = url.index('?si=')
    id = url[start_index:end_index]
    return redirect(id)

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

@app.route('/<playlist_id>/result/')
def display_result(playlist_id):
    global analyzers
    if(playlist_id in analyzers):
        result = analyzers[playlist_id].result
        analyzers[playlist_id] = None
        return render_template('results.html', id=playlist_id, result=result)
    else:
        return redirect(url_for('analyze_playlist', playlist_id=playlist_id))

if __name__ == '__main__':
    app.run(threaded=True)
from flask import Flask, request, render_template, redirect, url_for
from analyzer import PlaylistAnalyzer, update_result 
from admin import update_artists
import sys
import logging

app = Flask(__name__)
app.debug = True
log = logging.getLogger('werkzeug')
log.disabled = False

analyzers = {}

@app.route('/', methods=['GET'])
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
    analyzers[playlist_id] = None 
    analyzers[playlist_id] = PlaylistAnalyzer(playlist_id)
    analyzers[playlist_id].start()
    return render_template('loading.html', id=playlist_id)

@app.route('/analyzer-progress/<playlist_id>')
def get_progress(playlist_id):
    global analyzer
    if(playlist_id in analyzers):
        return str(analyzers[playlist_id].progress)
    else:
        return "0"

@app.route('/analyzer-result/<playlist_id>')
def get_analyzer_result(playlist_id):
    global analyzer
    if(playlist_id in analyzers):
        return analyzers[playlist_id].result

@app.route('/<playlist_id>/info/')
def get_playlist_info(playlist_id):
    global analyzers
    if(playlist_id in analyzers):
        if analyzers[playlist_id].playlist != None:
            return analyzers[playlist_id].playlist
        else:
            return ""
    else:
        return ""

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

@app.route('/<playlist_id>/check-us/')
def check_data(playlist_id):
    global analyzers
    if(playlist_id in analyzers):
        return render_template('check_data.html', artists=analyzers[playlist_id].artists)
    else:
        return redirect(url_for('analyze_playlist', playlist_id=playlist_id))

@app.route('/<playlist_id>/check-us/', methods=['POST'])
def change_artists(playlist_id):
    if(playlist_id in analyzers):
        print(request.json)
        update_artists(request.json)
        analyzers[playlist_id].artists = update_result(analyzers[playlist_id].artists, request.json)
        return redirect(url_for('display_result', playlist_id=playlist_id))
    else:
        return redirect(url_for('analyze_playlist', playlist_id=playlist_id))
    # return redirect('/' + playlist_id)

if __name__ == '__main__':
    app.run(threaded=True)
from flask import Flask, request, render_template
import logging
from analyzer import execute_query, execute_read_multiple_query, execute_read_query, escape_sql_string

app = Flask(__name__)
app.debug = True
log = logging.getLogger('werkzeug')
log.disabled = True

@app.route('/')
def admin_all_artists():
    all_artists = get_all_artists()
    return render_template('admin.html', artists=all_artists)

@app.route('/clean/')
def admin_clean_all_artists():
    all_artists = get_all_artists(clean=True)
    return render_template('admin.html', artists=all_artists)

@app.route('/', methods=['POST'])
def admin_change_artists():
    update_artists(request.json, admin=True)
    return request.json

def get_all_artists(playlist=None, clean=False):
    all_artists_dict = {}
    if(playlist == None):

        all_artists = execute_read_multiple_query("SELECT * from artists")
        for artist in all_artists:
            artist_dict = {
                "id": artist[0],
                "name": artist[1],
                "picture": artist[2],
                "popularity": artist[3],
                "votes_m": artist[4],
                "votes_f": artist[5],
                "votes_x": artist[6],
                "votes_mix": artist[7],
                "consensus": artist[8],
                "locked": artist[9],
            }
            all_artists_dict[artist[0]] = artist_dict

            if(clean):
                if(artist_dict['consensus'] == 'M' or artist_dict['consensus'] == 'MIX'):
                    execute_query(f"DELETE from recs WHERE artist_id='{artist_dict['id']}'")

    return all_artists_dict

def update_artists(updates_json, admin=False):
    for id in updates_json:
        artist = execute_read_query(f"SELECT * from artists WHERE spotify_id='{id}'")
        artist_dict = {
            "id": artist[0],
            "name": artist[1],
            "picture": artist[2],
            "popularity": artist[3],
            "votes_m": artist[4],
            "votes_f": artist[5],
            "votes_x": artist[6],
            "votes_mix": artist[7],
            "consensus": artist[8],
            "locked": artist[9],
        }
        if(not('category' in updates_json[id])):
            updates_json[id]['category'] = artist_dict['consensus']
        if(not('locked' in updates_json[id])):
            updates_json[id]['locked'] = artist_dict['locked']
        if(not(admin)):
            if(artist_dict['locked'] == 0):
                vote_category = ""
                if(updates_json[id]['category'] == 'M'):
                    artist_dict['votes_m'] += 1
                    vote_category = 'votes_m'
                elif(updates_json[id]['category'] == 'F'):
                    artist_dict['votes_f'] += 1
                    vote_category = 'votes_f'
                elif(updates_json[id]['category'] == 'X'):
                    artist_dict['votes_x'] += 1
                    vote_category = 'votes_x'
                elif(updates_json[id]['category'] == 'MIX'):
                    artist_dict['votes_mix'] += 1
                    vote_category = 'votes_mix'
                if(artist_dict[vote_category] == max(artist_dict['votes_m'], artist_dict['votes_f'], \
                    artist_dict['votes_x'], artist_dict['votes_mix'])):
                    artist_dict['consensus'] = updates_json[id]['category']
                execute_query(f"UPDATE artists SET {vote_category}={artist_dict[vote_category]}, consensus=" + \
                    f"'{artist_dict['consensus']}' WHERE spotify_id='{id}'")
        else:
            execute_query(f"UPDATE artists SET consensus='{updates_json[id]['category']}', locked={updates_json[id]['locked']} " + \
                f"WHERE spotify_id='{id}'")
            if(updates_json[id]['category'] == 'M' or updates_json[id]['category'] == 'MIX'):
                execute_query(f"DELETE from recs WHERE artist_id='{artist_dict['id']}'")

if __name__ == '__main__':
    app.run(threaded=True)
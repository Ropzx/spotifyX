from flask import Flask, redirect, request, session, url_for, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os, random

app = Flask(__name__)
app.secret_key = "secret"  # Replace with a secure key

sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="playlist-read-private playlist-modify-private playlist-modify-public ugc-image-upload"
)

@app.route("/")
def index():
    token_info = session.get("token_info", None)
    if not token_info:
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    return redirect(url_for("playlists"))


@app.route("/callback")
def callback():
    code = request.args.get("code")
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect(url_for("playlists"))

def get_spotify_client():
    token_info = session.get("token_info", None)
    if not token_info:
        return redirect(url_for("index"))
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session["token_info"] = token_info
    return spotipy.Spotify(auth=token_info["access_token"])


@app.route("/playlists")
def playlists():
    sp = get_spotify_client()
    playlists = sp.current_user_playlists()["items"]
    return render_template("playlists.html", playlists=playlists)

@app.route("/randomize", methods=["POST"])
def randomize():
    token_info = session.get("token_info")
    sp = spotipy.Spotify(auth=token_info["access_token"])
    playlist_id = request.form.get("playlist_id")

    # Fetch original playlist data
    original = sp.playlist(playlist_id)
    name = original["name"] + " (Shuffled)"
    description = "Shuffled version of " + original["name"]
    tracks = [track["track"]["uri"] for track in original["tracks"]["items"]]
    random.shuffle(tracks)

    # Create new playlist
    user_id = sp.current_user()["id"]
    new_playlist = sp.user_playlist_create(user_id, name, description=description, public=False)

    # Copy image
    if original["images"]:
        image_url = original["images"][0]["url"]
        import requests, base64
        img_data = base64.b64encode(requests.get(image_url).content).decode("utf-8")
        sp.playlist_upload_cover_image(new_playlist["id"], img_data)

    # Add shuffled tracks
    sp.playlist_add_items(new_playlist["id"], tracks)

    return f"✅ New shuffled playlist created: {name}"

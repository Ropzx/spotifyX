from flask import Flask, redirect, request, session, url_for, render_template
import os, random, requests, base64
import spotipy
from spotipy.oauth2 import SpotifyOAuth

app = Flask(__name__)
app.secret_key = "your-secret"  # Use a secure random secret in production

# Spotify authentication setup
sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="playlist-read-private playlist-modify-private playlist-modify-public ugc-image-upload"
)

# Helper: Get an authenticated Spotify client
def get_spotify_client():
    token_info = session.get("token_info")
    if not token_info:
        return None
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
        session["token_info"] = token_info
    return spotipy.Spotify(auth=token_info["access_token"])

# Homepage — redirect to login or playlists
@app.route("/")
def index():
    if "token_info" in session:
        return redirect("/playlists")
    return redirect(sp_oauth.get_authorize_url())

# Callback from Spotify
@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Authorization failed"
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect("/playlists")

# Playlist selection page
@app.route("/playlists")
def playlists():
    sp = get_spotify_client()
    if not sp:
        return redirect("/")
    playlists = sp.current_user_playlists()["items"]
    return render_template("playlists.html", playlists=playlists)

# Shuffle selected playlist and create a new one
@app.route("/randomize", methods=["POST"])
def randomize():
    sp = get_spotify_client()
    if not sp:
        return redirect("/")
    
    playlist_id = request.form.get("playlist_id")
    original = sp.playlist(playlist_id)
    tracks = [item["track"]["uri"] for item in original["tracks"]["items"]]
    random.shuffle(tracks)

    new_playlist = sp.user_playlist_create(
        sp.current_user()["id"],
        original["name"] + " (Shuffled)",
        description="Shuffled version of " + original["name"],
        public=False
    )

    # Copy playlist cover image if it exists
    if original["images"]:
        img = base64.b64encode(requests.get(original["images"][0]["url"]).content).decode("utf-8")
        sp.playlist_upload_cover_image(new_playlist["id"], img)

    sp.playlist_add_items(new_playlist["id"], tracks)

    return f"✅ New shuffled playlist created: <b>{original['name']} (Shuffled)</b>"

# Run the app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

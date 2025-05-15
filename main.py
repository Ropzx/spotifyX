from flask import Flask, redirect, request, session, url_for, render_template
import os, random, requests, base64
import spotipy
from spotipy.oauth2 import SpotifyOAuth

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# ✅ Render is HTTPS, so cookies must be secure
app.config['SESSION_COOKIE_SECURE'] = True

# Setup Spotify auth
sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="playlist-read-private playlist-modify-private playlist-modify-public ugc-image-upload"
)

def get_spotify_client():
    token_info = session.get("token_info")
    if not token_info:
        return None

    if sp_oauth.is_token_expired(token_info):
        try:
            token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
            session["token_info"] = token_info
        except Exception:
            session.pop("token_info", None)
            return None

    return spotipy.Spotify(auth=token_info["access_token"])

@app.route("/")
def index():
    if "token_info" in session:
        return redirect("/playlists")
    return redirect(sp_oauth.get_authorize_url())

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Authorization failed."
    
    try:
        token_info = sp_oauth.get_access_token(code)
        session["token_info"] = token_info
    except Exception as e:
        return f"Auth error: {e}"
    
    return redirect("/playlists")

@app.route("/playlists")
def playlists():
    sp = get_spotify_client()
    if not sp:
        return redirect(url_for("index"))

    try:
        playlists = sp.current_user_playlists()["items"]
    except:
        session.pop("token_info", None)
        return redirect(url_for("index"))

    return render_template("playlists.html", playlists=playlists)

@app.route("/randomize", methods=["POST"])
def randomize():
    sp = get_spotify_client()
    if not sp:
        return redirect("/")

    try:
        playlist_id = request.form.get("playlist_id")
        if not playlist_id:
            return "❌ No playlist ID provided."

        original = sp.playlist(playlist_id)
        tracks_data = original["tracks"]["items"]
        
        if not tracks_data:
            return "❌ No tracks found in this playlist."

        tracks = [item["track"]["uri"] for item in tracks_data if item["track"]]
        random.shuffle(tracks)

        new_playlist = sp.user_playlist_create(
            sp.current_user()["id"],
            original["name"] + " (Shuffled)",
            description="Shuffled version of " + original["name"],
            public=False
        )

        # Copy cover image if exists
        if original["images"]:
            try:
                img_data = requests.get(original["images"][0]["url"]).content
                img_b64 = base64.b64encode(img_data).decode("utf-8")
                sp.playlist_upload_cover_image(new_playlist["id"], img_b64)
            except Exception as e:
                print("⚠️ Failed to upload image:", str(e))

        sp.playlist_add_items(new_playlist["id"], tracks)

        return f"""
        <html>
            <head><title>Playlist Created</title></head>
            <body style='text-align:center; font-family:sans-serif; background:#121212; color:white;'>
                <h1>✅ New Shuffled Playlist Created</h1>
                <p>{original['name']} → {original['name']} (Shuffled)</p>
                <a href="/playlists" style="color:#1DB954;">← Back to Playlists</a>
            </body>
        </html>
        """

    except Exception as e:
        print("❌ Error in /randomize:", str(e))
        return f"<h2 style='color:red;'>Something went wrong: {str(e)}</h2>"


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

from flask import Flask, redirect, request, session, url_for, render_template
import os, random, requests, base64, threading
import spotipy
from spotipy.oauth2 import SpotifyOAuth

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config['SESSION_COOKIE_SECURE'] = True

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
        return redirect(url_for("playlists"))
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
    return redirect(url_for("playlists"))

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

    playlist_id = request.form.get("playlist_id")
    if not playlist_id:
        return "❌ No playlist ID provided."

    def process_playlist(sp, playlist_id):
        try:
            original = sp.playlist(playlist_id)
            tracks = []
            offset = 0
            limit = 100
            while True:
                response = sp.playlist_items(
                    playlist_id,
                    offset=offset,
                    limit=limit,
                    fields="items.track.uri,total",
                    additional_types=["track"]
                )
                batch = [item["track"]["uri"] for item in response["items"] if item["track"]]
                if not batch:
                    break
                tracks.extend(batch)
                offset += limit

            if not tracks:
                print("❌ No tracks found.")
                return

            random.shuffle(tracks)

            user_id = sp.current_user()["id"]
            new_playlist = sp.user_playlist_create(
                user_id,
                f"{original['name']} (Shuffled)",
                description=f"Shuffled version of {original['name']}",
                public=False
            )

            if original["images"]:
                try:
                    img_data = requests.get(original["images"][0]["url"]).content
                    img_b64 = base64.b64encode(img_data).decode("utf-8")
                    sp.playlist_upload_cover_image(new_playlist["id"], img_b64)
                except Exception as e:
                    print("⚠️ Image upload failed:", e)

            for i in range(0, len(tracks), 100):
                sp.playlist_add_items(new_playlist["id"], tracks[i:i + 100])

            print(f"✅ Created playlist: {new_playlist['external_urls']['spotify']}")

        except Exception as e:
            print("❌ Error in background processing:", str(e))

    thread = threading.Thread(target=process_playlist, args=(sp, playlist_id))
    thread.start()

    return """
    <html>
        <head><title>Shuffling...</title>
        <link rel="stylesheet" href="/static/style.css">
        </head>
        <body style='text-align:center; font-family:sans-serif; background:#121212; color:white;'>
            <h1>🎶 Shuffling Your Playlist...</h1>
            <p>This may take up to a minute for large playlists.</p>
            <a href="/playlists" style="color:#1DB954;">← Back to Playlists</a>
        </body>
    </html>
    """

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

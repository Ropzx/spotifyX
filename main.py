from flask import Flask, redirect, request, session, url_for, render_template, Response
import os, random, requests, base64
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

    def generate():
        try:
            original = sp.playlist(playlist_id)
            yield "<p>✅ Fetched playlist details...</p>"

            tracks = []
            offset = 0
            limit = 100
            total = 0
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
                total += len(batch)
                yield f"<p>📦 Fetched {total} tracks...</p>"
                offset += limit

            if not tracks:
                yield "<p>❌ No tracks found.</p>"
                return

            random.shuffle(tracks)
            yield f"<p>🔀 Shuffled {len(tracks)} tracks...</p>"

            user_id = sp.current_user()["id"]
            new_playlist = sp.user_playlist_create(
                user_id,
                f"{original['name']} (Shuffled)",
                description=f"Shuffled version of {original['name']}",
                public=False
            )
            yield f"<p>🆕 Created new playlist: <a style='color:#1DB954;' href='{new_playlist['external_urls']['spotify']}' target='_blank'>Open on Spotify</a></p>"

            if original["images"]:
                try:
                    img_data = requests.get(original["images"][0]["url"]).content
                    img_b64 = base64.b64encode(img_data).decode("utf-8")
                    sp.playlist_upload_cover_image(new_playlist["id"], img_b64)
                    yield "<p>🖼️ Copied playlist image</p>"
                except Exception as e:
                    yield f"<p>⚠️ Image upload failed: {e}</p>"

            for i in range(0, len(tracks), 100):
                sp.playlist_add_items(new_playlist["id"], tracks[i:i + 100])
                yield f"<p>➕ Added tracks {i+1} - {min(i+100, len(tracks))}</p>"

            yield "<h2 style='color:#1DB954;'>✅ Done!</h2>"
        except Exception as e:
            yield f"<p style='color:red;'>❌ Error: {str(e)}</p>"

    return Response(
        f"""
        <html>
            <head>
                <title>Shuffling...</title>
                <link rel="stylesheet" href="/static/style.css">
            </head>
            <body style='font-family:sans-serif; background:#121212; color:white; padding:20px;'>
                <h1>🎶 Shuffling Your Playlist...</h1>
                <div id="log">
                    {''.join(generate())}
                </div>
                <a href="/playlists" style="color:#1DB954;">← Back to Playlists</a>
            </body>
        </html>
        """, mimetype='text/html'
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

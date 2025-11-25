"""
API for polling hoarder and generating podcast feed
"""

import os

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, Response, render_template, request, send_file, send_from_directory
from flask_restx import Api, Resource, fields

from hoarderpod.config import Config
from hoarderpod.episodes import EpisodeOps
from hoarderpod.run import gen_feed, poll_hoarder_and_tts
from hoarderpod.tts_service import TTSService

# Initialize TTS service to get MP3_STORAGE_PATH
tts_service = TTSService()

sched = BackgroundScheduler(daemon=True)
sched.add_job(poll_hoarder_and_tts, "interval", minutes=Config.POLL_INTERVAL_MINUTES)
sched.start()

app = Flask(__name__)
episode_ops = EpisodeOps()


@app.route("/")
def show_episodes():
    """Show episodes list in HTML format"""
    episodes = episode_ops.get_all_episodes(sort_by_created_at=True)
    return render_template("episodes.html", episodes=episodes)


api = Api(
    app, version="1.0", title="Hoarder Episodes API", description="API for accessing Hoarder episodes", doc="/docs"
)

ns = api.namespace("episodes", path="/episodes", description="Episode operations")

# Define the episode model for swagger documentation
episode_model = api.model(
    "Episode",
    {
        "id": fields.String(required=True, description="Episode ID"),
        "title": fields.String(required=True, description="Episode title"),
        "description": fields.String(description="Episode description"),
        "authors": fields.Raw(description="Episode authors"),
        "url": fields.String(description="Episode URL"),
        "created_at": fields.DateTime(description="Creation timestamp"),
        "crawled_at": fields.DateTime(description="Crawl timestamp"),
        "tts_job_id": fields.String(description="TTS job ID"),
        "mp3": fields.String(description="MP3 file path"),
    },
)


@ns.route("/")
class EpisodeList(Resource):
    @ns.doc("list_episodes")
    @ns.marshal_list_with(episode_model)
    def get(self):
        """List all episodes"""
        return episode_ops.get_all_episodes()


@ns.route("/<episode_id>")
class Episode(Resource):
    @ns.doc("delete_episode")
    def delete(self, episode_id):
        """Delete an episode"""
        print("Deleting episode", episode_id)
        num_deleted = episode_ops.delete_episode(episode_id)
        if num_deleted == 0:
            return "Episode not found", 404
        return "OK"


@ns.route("/tts/<episode_id>")
class Episode(Resource):
    @ns.doc("request_new_tts")
    def delete(self, episode_id):
        """Request new TTS run for an episode"""

        print("Requesting new TTS run for episode", episode_id)

        if episode_id not in episode_ops.get_episode_ids():
            return "Episode not found", 404

        mp3_path = episode_ops.get_episode_mp3(episode_id)
        if mp3_path and os.path.exists(mp3_path):
            os.remove(mp3_path)

        episode_ops.clear_tts(episode_id)
        poll_hoarder_and_tts()
        return "OK"


@ns.route("/tts_waiting")
class TTSWaiting(Resource):
    @ns.doc("list_episodes_waiting_for_tts")
    @ns.marshal_list_with(episode_model)
    def get(self):
        """Get the list of episodes that are waiting for TTS"""
        return episode_ops.get_episodes_to_tts()


@ns.route("/force_update")
class ForceUpdate(Resource):
    @ns.doc("force_update")
    def get(self):
        """Force update the episodes"""
        poll_hoarder_and_tts()
        return "OK"


@ns.route("/feed")
class Feed(Resource):
    @ns.doc("get_feed")
    def get(self):
        """Get the feed"""
        episodes = episode_ops.get_episodes_with_mp3()
        # Limit to most recent episodes (reverse order since episodes are sorted oldest first)
        episodes = episodes[-Config.FEED_MAX_EPISODES:] if len(episodes) > Config.FEED_MAX_EPISODES else episodes
        feed_str = gen_feed(episodes, request.url_root)
        return Response(feed_str, mimetype="application/rss+xml")


@app.route("/feed")
@app.route("/feed.xml")
@app.route("/feed.rss")
@app.route("/rss")
@app.route("/atom")
def feed():
    """Hidden alternate routes to get the feed"""
    return Feed().get()


@app.route("/cover.jpg")
def cover():
    """Get the cover image"""
    return send_file(os.path.join(app.root_path, "../cover.jpg"), mimetype="image/jpeg")


@app.route("/feed.svg")
def feed_img():
    """Get the feed image"""
    return send_file(os.path.join(app.root_path, "../feed.svg"), mimetype="image/svg+xml")


@app.route("/audio/<path:filename>")
def serve_audio(filename):
    """Serve audio files"""
    return send_from_directory(tts_service.mp3_storage_path, filename)


if __name__ == "__main__":
    env = Config.FLASK_ENV
    port = Config.PORT
    if env and env.lower().startswith("dev"):
        app.run(debug=True, host="0.0.0.0", port=port)
    else:
        import waitress

        waitress.serve(app, host="0.0.0.0", port=port)

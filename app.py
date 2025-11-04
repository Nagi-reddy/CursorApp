from flask import Flask, render_template, request, send_file, redirect, url_for, flash, after_this_request
import tempfile
import os
import re
import logging
BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "..", "templates")

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# Optional: handle missing pytube gracefully
try:
    from pytube import YouTube
except ImportError:
    YouTube = None  # will be checked at request time

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")

logging.basicConfig(level=logging.INFO)

def sanitize_filename(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-\. ]', '_', name)[:150]

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url", "").strip()

    if not url:
        flash("Please provide a YouTube URL.")
        return redirect(url_for("index"))

    if YouTube is None:
        flash("Server missing dependency 'pytube'. Please install it in the active environment.")
        return redirect(url_for("index"))

    # Quick URL validation to avoid obvious bad inputs
    if "youtube.com/watch" not in url and "youtu.be/" not in url:
        flash("Please enter a valid YouTube link.")
        return redirect(url_for("index"))

    try:
        yt = YouTube(url)
        app.logger.info("Resolving streams for %s", yt.watch_url)

        stream = (
            yt.streams
              .filter(progressive=True, file_extension="mp4")
              .order_by("resolution")
              .desc()
              .first()
        )

        if not stream:
            flash("No MP4 progressive stream available for this video. Try another URL.")
            return redirect(url_for("index"))

        tmp_dir = tempfile.mkdtemp()
        out_path = stream.download(output_path=tmp_dir, filename="video.mp4")
        filename = sanitize_filename(f"{yt.title}.mp4")

        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(out_path):
                    os.remove(out_path)
                if os.path.isdir(tmp_dir):
                    os.rmdir(tmp_dir)
            except Exception:
                pass
            return response

        return send_file(out_path, as_attachment=True, download_name=filename, mimetype="video/mp4")

    except Exception as e:
        app.logger.exception("Download failed")
        flash(f"Failed to process the URL: {type(e).__name__}: {e}")
        return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=True)
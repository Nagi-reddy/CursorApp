from flask import Flask, render_template, request, send_file, redirect, url_for, flash, after_this_request
import tempfile
import os
import re
import logging

BASE_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

app = Flask(__name__, template_folder=TEMPLATE_DIR)
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

    # Normalize YouTube URLs
    if "youtu.be/" in url:
        url = url.replace("youtu.be/", "youtube.com/watch?v=")
    if "youtube.com/watch" not in url and "youtube.com/shorts" not in url:
        flash("Please enter a valid YouTube link.")
        return redirect(url_for("index"))

    try:
        import yt_dlp
        
        tmp_dir = tempfile.mkdtemp()
        out_path = os.path.join(tmp_dir, "video")
        
        # Configuration to avoid 403 Forbidden errors
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': out_path + '.%(ext)s',
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            # Headers to avoid 403 errors
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            },
            # Additional options to avoid detection
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                app.logger.info(f"Attempting to download: {url}")
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'video')
                filename_base = sanitize_filename(title)
                
                # Find the downloaded file
                downloaded_file = None
                ext = 'mp4'
                for f in os.listdir(tmp_dir):
                    if f.startswith('video'):
                        downloaded_file = os.path.join(tmp_dir, f)
                        if '.' in f:
                            ext = f.split('.')[-1]
                        break
                
                if not downloaded_file or not os.path.exists(downloaded_file):
                    flash("Download failed - file was not created.")
                    return redirect(url_for("index"))
                
                final_filename = f"{filename_base}.{ext}"
                
                @after_this_request
                def cleanup(response):
                    try:
                        if os.path.exists(downloaded_file):
                            os.remove(downloaded_file)
                        if os.path.isdir(tmp_dir):
                            try:
                                os.rmdir(tmp_dir)
                            except OSError:
                                pass
                    except Exception:
                        pass
                    return response
                
                return send_file(
                    downloaded_file,
                    as_attachment=True,
                    download_name=final_filename,
                    mimetype=f"video/{ext}"
                )
                
        except yt_dlp.utils.DownloadError as e:
            error_str = str(e)
            app.logger.error(f"yt-dlp DownloadError: {error_str}")
            
            if "HTTP Error 403" in error_str or "403" in error_str:
                flash("YouTube blocked the request (403). Try: 1) Update yt-dlp: pip install --upgrade yt-dlp, 2) Try a different video, or 3) Wait a few minutes and try again.")
            elif "HTTP Error 400" in error_str or "400" in error_str:
                flash(f"YouTube returned 400 error: {error_str[:200]}")
            elif "Private video" in error_str:
                flash("This video is private and cannot be downloaded.")
            elif "Video unavailable" in error_str:
                flash("This video is unavailable.")
            else:
                flash(f"Download error: {error_str[:300]}")
            return redirect(url_for("index"))
            
    except ImportError:
        flash("yt-dlp is not installed. Run: pip install yt-dlp")
        return redirect(url_for("index"))
    except Exception as e:
        error_str = str(e)
        error_type = type(e).__name__
        app.logger.error(f"Exception type: {error_type}, Message: {error_str}")
        
        if "403" in error_str or "Forbidden" in error_str:
            flash("YouTube blocked the request. Try updating yt-dlp: pip install --upgrade yt-dlp")
        else:
            flash(f"Error ({error_type}): {error_str[:300]}")
        return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=True)
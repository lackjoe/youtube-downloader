"""yt-dlp wrapper for YouTube downloading."""

import threading
from pathlib import Path
from typing import Callable, Optional

import yt_dlp


class VideoInfo:
    """Stores fetched video metadata."""

    def __init__(self, data: dict):
        self.title: str = data.get("title", "Unknown")
        self.channel: str = data.get("channel", data.get("uploader", "Unknown"))
        self.duration: int = data.get("duration", 0)
        self.thumbnail: str = data.get("thumbnail", "")
        self.url: str = data.get("webpage_url", "")
        self.is_playlist: bool = data.get("_type") == "playlist"
        self.entries: list[dict] = data.get("entries", []) if self.is_playlist else []
        self.playlist_count: int = data.get("playlist_count", len(self.entries))

    @property
    def duration_str(self) -> str:
        if self.duration <= 0:
            return "Unknown"
        h, rem = divmod(self.duration, 3600)
        m, s = divmod(rem, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


# Format option constants
FORMAT_VIDEO_AUDIO = "video_audio"
FORMAT_VIDEO_ONLY = "video_only"
FORMAT_AUDIO_ONLY = "audio_only"

VIDEO_QUALITIES = ["best", "1080", "720", "480", "360"]
VIDEO_QUALITY_LABELS = {
    "best": "Best Quality",
    "1080": "1080p",
    "720": "720p",
    "480": "480p",
    "360": "360p",
}

AUDIO_QUALITIES = ["320", "192", "128"]
AUDIO_QUALITY_LABELS = {
    "320": "320 kbps",
    "192": "192 kbps",
    "128": "128 kbps",
}


class Downloader:
    """Wraps yt-dlp for fetching info and downloading."""

    def __init__(self):
        self._cancel_event = threading.Event()

    def fetch_info(self, url: str) -> VideoInfo:
        """Fetch video/playlist metadata without downloading."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)
        return VideoInfo(data)

    def cancel(self):
        """Signal cancellation for in-progress download."""
        self._cancel_event.set()

    def download(
        self,
        url: str,
        output_dir: str,
        fmt: str = FORMAT_VIDEO_AUDIO,
        quality: str = "best",
        progress_callback: Optional[Callable[[dict], None]] = None,
    ):
        """Download a single video/audio.

        Args:
            url: YouTube URL.
            output_dir: Directory to save files.
            fmt: One of FORMAT_VIDEO_AUDIO, FORMAT_VIDEO_ONLY, FORMAT_AUDIO_ONLY.
            quality: Video resolution string or audio bitrate string.
            progress_callback: Called with progress dict containing
                'status', 'downloaded_bytes', 'total_bytes', 'speed', 'eta', 'filename'.
        """
        self._cancel_event.clear()
        output_path = str(Path(output_dir) / "%(title)s.%(ext)s")

        opts: dict = {
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        # Format selection
        if fmt == FORMAT_AUDIO_ONLY:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": quality,
                }
            ]
        elif fmt == FORMAT_VIDEO_ONLY:
            if quality == "best":
                opts["format"] = "bestvideo[ext=mp4]/bestvideo"
            else:
                opts["format"] = (
                    f"bestvideo[height<={quality}][ext=mp4]/"
                    f"bestvideo[height<={quality}]/bestvideo"
                )
        else:  # video + audio
            if quality == "best":
                opts["format"] = (
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                    "bestvideo+bestaudio/best"
                )
            else:
                opts["format"] = (
                    f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"bestvideo[height<={quality}]+bestaudio/best"
                )
            opts["merge_output_format"] = "mp4"

        # Progress hook
        def _hook(d: dict):
            if self._cancel_event.is_set():
                raise yt_dlp.utils.DownloadError("Cancelled by user")
            if progress_callback:
                progress_callback(d)

        opts["progress_hooks"] = [_hook]

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

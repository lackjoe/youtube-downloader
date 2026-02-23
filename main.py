"""YouTube Downloader - CustomTkinter GUI Application."""

import io
import os
import ssl
import sys
import threading
from pathlib import Path
from tkinter import filedialog
from urllib.request import urlopen

# Fix SSL certificate issue in PyInstaller bundle
if getattr(sys, "frozen", False):
    import certifi
    os.environ["SSL_CERT_FILE"] = certifi.where()
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

import customtkinter as ctk
from PIL import Image

from downloader import (
    AUDIO_QUALITIES,
    AUDIO_QUALITY_LABELS,
    VIDEO_QUALITIES,
    VIDEO_QUALITY_LABELS,
    FORMAT_AUDIO_ONLY,
    FORMAT_VIDEO_AUDIO,
    FORMAT_VIDEO_ONLY,
    Downloader,
    VideoInfo,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DEFAULT_OUTPUT = str(Path.home() / "Downloads")


class QueueItem:
    """Represents one item in the download queue."""

    STATUS_PENDING = "pending"
    STATUS_DOWNLOADING = "downloading"
    STATUS_DONE = "done"
    STATUS_ERROR = "error"

    def __init__(self, url: str, title: str, fmt: str, quality: str):
        self.url = url
        self.title = title
        self.fmt = fmt
        self.quality = quality
        self.status = self.STATUS_PENDING
        self.error_msg = ""


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Downloader")
        self.geometry("700x780")
        self.minsize(620, 700)

        self.downloader = Downloader()
        self.current_info: VideoInfo | None = None
        self.output_dir = DEFAULT_OUTPUT
        self.queue: list[QueueItem] = []
        self.is_downloading = False

        self._build_ui()

    # ── UI Construction ──────────────────────────────────────────────

    def _build_ui(self):
        # Title
        ctk.CTkLabel(
            self, text="YouTube Downloader", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=(18, 6))

        # URL row
        url_frame = ctk.CTkFrame(self, fg_color="transparent")
        url_frame.pack(fill="x", padx=20, pady=(4, 8))

        self.url_entry = ctk.CTkEntry(url_frame, placeholder_text="YouTube URL을 입력하세요")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.url_entry.bind("<Return>", lambda _: self._fetch_info())

        self.fetch_btn = ctk.CTkButton(url_frame, text="정보 조회", width=100, command=self._fetch_info)
        self.fetch_btn.pack(side="right")

        # Info panel
        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.pack(fill="x", padx=20, pady=(0, 8))

        self.thumb_label = ctk.CTkLabel(self.info_frame, text="", width=192, height=108)
        self.thumb_label.grid(row=0, column=0, rowspan=3, padx=10, pady=10)

        self.title_label = ctk.CTkLabel(
            self.info_frame, text="영상 정보가 여기에 표시됩니다",
            font=ctk.CTkFont(size=14, weight="bold"), wraplength=420, anchor="w", justify="left",
        )
        self.title_label.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=(10, 2))

        self.channel_label = ctk.CTkLabel(self.info_frame, text="", anchor="w")
        self.channel_label.grid(row=1, column=1, sticky="w", padx=(0, 10))

        self.duration_label = ctk.CTkLabel(self.info_frame, text="", anchor="w")
        self.duration_label.grid(row=2, column=1, sticky="w", padx=(0, 10), pady=(0, 10))

        self.info_frame.columnconfigure(1, weight=1)

        # Format selection
        fmt_frame = ctk.CTkFrame(self, fg_color="transparent")
        fmt_frame.pack(fill="x", padx=20, pady=(0, 4))

        ctk.CTkLabel(fmt_frame, text="포맷:").pack(side="left", padx=(0, 8))

        self.format_var = ctk.StringVar(value=FORMAT_VIDEO_AUDIO)
        for label, val in [("영상+오디오", FORMAT_VIDEO_AUDIO), ("영상만", FORMAT_VIDEO_ONLY), ("오디오만(MP3)", FORMAT_AUDIO_ONLY)]:
            ctk.CTkRadioButton(fmt_frame, text=label, variable=self.format_var, value=val, command=self._on_format_change).pack(side="left", padx=6)

        # Quality selection
        qual_frame = ctk.CTkFrame(self, fg_color="transparent")
        qual_frame.pack(fill="x", padx=20, pady=(0, 4))

        ctk.CTkLabel(qual_frame, text="품질:").pack(side="left", padx=(0, 8))

        self.quality_menu = ctk.CTkOptionMenu(qual_frame, width=160, values=list(VIDEO_QUALITY_LABELS.values()))
        self.quality_menu.pack(side="left")
        self.quality_menu.set(VIDEO_QUALITY_LABELS["720"])

        # Output directory
        dir_frame = ctk.CTkFrame(self, fg_color="transparent")
        dir_frame.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkLabel(dir_frame, text="저장:").pack(side="left", padx=(0, 8))

        self.dir_label = ctk.CTkLabel(dir_frame, text=self.output_dir, anchor="w")
        self.dir_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(dir_frame, text="변경", width=60, command=self._choose_dir).pack(side="right")

        # Progress
        prog_frame = ctk.CTkFrame(self, fg_color="transparent")
        prog_frame.pack(fill="x", padx=20, pady=(0, 4))

        self.progress_bar = ctk.CTkProgressBar(prog_frame)
        self.progress_bar.pack(fill="x", side="left", expand=True, padx=(0, 10))
        self.progress_bar.set(0)

        self.progress_pct = ctk.CTkLabel(prog_frame, text="0%", width=45)
        self.progress_pct.pack(side="right")

        self.status_label = ctk.CTkLabel(self, text="대기 중", text_color="gray")
        self.status_label.pack(pady=(0, 4))

        # Action buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 8))

        self.add_queue_btn = ctk.CTkButton(btn_frame, text="큐에 추가", width=140, command=self._add_to_queue)
        self.add_queue_btn.pack(side="left", padx=(0, 8))

        self.download_btn = ctk.CTkButton(
            btn_frame, text="다운로드 시작", width=200,
            fg_color="#28a745", hover_color="#218838", command=self._start_download,
        )
        self.download_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.cancel_btn = ctk.CTkButton(
            btn_frame, text="취소", width=80,
            fg_color="#dc3545", hover_color="#c82333", command=self._cancel_download, state="disabled",
        )
        self.cancel_btn.pack(side="right")

        # Queue / History
        ctk.CTkLabel(self, text="다운로드 큐 / 이력", font=ctk.CTkFont(size=14, weight="bold"), anchor="w").pack(
            fill="x", padx=20, pady=(8, 2)
        )

        self.queue_frame = ctk.CTkScrollableFrame(self, height=200)
        self.queue_frame.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        self.queue_placeholder = ctk.CTkLabel(self.queue_frame, text="큐가 비어 있습니다", text_color="gray")
        self.queue_placeholder.pack(pady=20)

    # ── Format Change ────────────────────────────────────────────────

    def _on_format_change(self):
        fmt = self.format_var.get()
        if fmt == FORMAT_AUDIO_ONLY:
            self.quality_menu.configure(values=list(AUDIO_QUALITY_LABELS.values()))
            self.quality_menu.set(AUDIO_QUALITY_LABELS["192"])
        else:
            self.quality_menu.configure(values=list(VIDEO_QUALITY_LABELS.values()))
            self.quality_menu.set(VIDEO_QUALITY_LABELS["720"])

    def _get_quality_key(self) -> str:
        """Map the displayed quality label back to its key."""
        current = self.quality_menu.get()
        fmt = self.format_var.get()
        labels = AUDIO_QUALITY_LABELS if fmt == FORMAT_AUDIO_ONLY else VIDEO_QUALITY_LABELS
        for key, label in labels.items():
            if label == current:
                return key
        return "best"

    # ── Directory Picker ─────────────────────────────────────────────

    def _choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.output_dir)
        if d:
            self.output_dir = d
            self.dir_label.configure(text=d)

    # ── Fetch Info ───────────────────────────────────────────────────

    def _fetch_info(self):
        url = self.url_entry.get().strip()
        if not url:
            self._set_status("URL을 입력하세요", "orange")
            return

        self.fetch_btn.configure(state="disabled")
        self._set_status("정보 조회 중...", "gray")
        self.title_label.configure(text="로딩 중...")
        self.channel_label.configure(text="")
        self.duration_label.configure(text="")

        def _work():
            try:
                info = self.downloader.fetch_info(url)
                self.current_info = info
                self.after(0, lambda: self._display_info(info))
            except Exception as e:
                self.after(0, lambda: self._set_status(f"조회 실패: {e}", "red"))
                self.after(0, lambda: self.title_label.configure(text="조회 실패"))
            finally:
                self.after(0, lambda: self.fetch_btn.configure(state="normal"))

        threading.Thread(target=_work, daemon=True).start()

    def _display_info(self, info: VideoInfo):
        if info.is_playlist:
            self.title_label.configure(text=f"[재생목록] {info.title}")
            self.channel_label.configure(text=f"채널: {info.channel}")
            self.duration_label.configure(text=f"영상 수: {info.playlist_count}개")
        else:
            self.title_label.configure(text=info.title)
            self.channel_label.configure(text=f"채널: {info.channel}")
            self.duration_label.configure(text=f"길이: {info.duration_str}")

        self._set_status("정보 조회 완료", "#28a745")

        # Load thumbnail in background
        if info.thumbnail:
            threading.Thread(target=self._load_thumbnail, args=(info.thumbnail,), daemon=True).start()

    def _load_thumbnail(self, url: str):
        try:
            data = urlopen(url, timeout=10).read()
            img = Image.open(io.BytesIO(data))
            img = img.resize((192, 108), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(192, 108))
            self.after(0, lambda: self.thumb_label.configure(image=ctk_img, text=""))
            self._thumb_ref = ctk_img  # prevent GC
        except Exception:
            pass

    # ── Queue Management ─────────────────────────────────────────────

    def _add_to_queue(self):
        url = self.url_entry.get().strip()
        if not url:
            self._set_status("URL을 입력하세요", "orange")
            return

        info = self.current_info
        fmt = self.format_var.get()
        quality = self._get_quality_key()

        if info and info.is_playlist:
            for entry in info.entries:
                entry_url = entry.get("url") or entry.get("webpage_url", "")
                entry_title = entry.get("title", "Unknown")
                if entry_url:
                    self.queue.append(QueueItem(entry_url, entry_title, fmt, quality))
        else:
            title = info.title if info else url
            self.queue.append(QueueItem(url, title, fmt, quality))

        self._refresh_queue_ui()
        self._set_status(f"큐에 추가됨 (총 {len(self.queue)}개)", "#28a745")

    def _refresh_queue_ui(self):
        for widget in self.queue_frame.winfo_children():
            widget.destroy()

        if not self.queue:
            ctk.CTkLabel(self.queue_frame, text="큐가 비어 있습니다", text_color="gray").pack(pady=20)
            return

        for i, item in enumerate(self.queue):
            row = ctk.CTkFrame(self.queue_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)

            if item.status == QueueItem.STATUS_DONE:
                icon, color = "✅", "#28a745"
            elif item.status == QueueItem.STATUS_DOWNLOADING:
                icon, color = "⏳", "#ffc107"
            elif item.status == QueueItem.STATUS_ERROR:
                icon, color = "❌", "#dc3545"
            else:
                icon, color = "⏸", "gray"

            ctk.CTkLabel(row, text=f"{i + 1}.", width=30).pack(side="left")
            ctk.CTkLabel(row, text=item.title, anchor="w", wraplength=400).pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(row, text=icon, text_color=color, width=30).pack(side="right", padx=(4, 0))

            if item.status == QueueItem.STATUS_PENDING:
                def _remove(idx=i):
                    self.queue.pop(idx)
                    self._refresh_queue_ui()
                ctk.CTkButton(row, text="✕", width=28, height=28, fg_color="#dc3545", hover_color="#c82333", command=_remove).pack(side="right", padx=2)

    # ── Download ─────────────────────────────────────────────────────

    def _start_download(self):
        # If queue is empty, add current URL first
        if not self.queue:
            self._add_to_queue()
        if not self.queue:
            return

        self.is_downloading = True
        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.add_queue_btn.configure(state="disabled")

        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self):
        for item in self.queue:
            if item.status != QueueItem.STATUS_PENDING:
                continue

            item.status = QueueItem.STATUS_DOWNLOADING
            self.after(0, self._refresh_queue_ui)
            self.after(0, lambda t=item.title: self._set_status(f"다운로드 중: {t}", "#ffc107"))

            try:
                self.downloader.download(
                    url=item.url,
                    output_dir=self.output_dir,
                    fmt=item.fmt,
                    quality=item.quality,
                    progress_callback=lambda d: self.after(0, lambda d=d: self._on_progress(d)),
                )
                item.status = QueueItem.STATUS_DONE
            except Exception as e:
                item.status = QueueItem.STATUS_ERROR
                item.error_msg = str(e)
                if "Cancelled" in str(e):
                    self.after(0, lambda: self._set_status("다운로드 취소됨", "orange"))
                    break

            self.after(0, self._refresh_queue_ui)

        self.after(0, self._download_finished)

    def _on_progress(self, d: dict):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = downloaded / total
                self.progress_bar.set(pct)
                self.progress_pct.configure(text=f"{int(pct * 100)}%")
            speed = d.get("speed")
            if speed:
                speed_str = f"{speed / 1024 / 1024:.1f} MB/s"
                self._set_status(f"다운로드 중... {speed_str}", "#ffc107")
        elif d.get("status") == "finished":
            self.progress_bar.set(1.0)
            self.progress_pct.configure(text="100%")

    def _download_finished(self):
        self.is_downloading = False
        self.download_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.add_queue_btn.configure(state="normal")

        done = sum(1 for q in self.queue if q.status == QueueItem.STATUS_DONE)
        errors = sum(1 for q in self.queue if q.status == QueueItem.STATUS_ERROR)
        total = len(self.queue)
        self._set_status(f"완료: {done}/{total} 성공, {errors} 실패", "#28a745" if errors == 0 else "orange")

    def _cancel_download(self):
        self.downloader.cancel()

    # ── Helpers ───────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str = "gray"):
        self.status_label.configure(text=text, text_color=color)


if __name__ == "__main__":
    app = App()
    app.mainloop()

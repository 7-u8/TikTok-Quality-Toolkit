"""Check a posted TikTok: which frame rates / resolutions TikTok serves.

Primary source: TikTok's own video page (the rehydration JSON lists every
stream with its fps, size, codec and bitrate). Fallback: the tikwm.com API
(as used by HaiYTB/TikTok-Tweaks), whose file is downloaded and inspected.
"""

import http.cookiejar
import json
import os
import re
import urllib.parse
import urllib.request

from .mp4 import Mp4Error

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
URL_RE = re.compile(r"https?://(?:[\w-]+\.)?tiktok\.com/[^\s\"'<>]+", re.I)
CODECS = {"h264": "H.264", "h265_hvc1": "H.265", "bytevc1": "H.265", "h265": "H.265"}


class Session:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.opener.addheaders = [("User-Agent", UA), ("Accept-Language", "en-US,en;q=0.9")]

    def get(self, url, headers=None, data=None, timeout=25):
        req = urllib.request.Request(url, data=data, headers=headers or {})
        return self.opener.open(req, timeout=timeout)


def extract_url(text):
    m = URL_RE.search(text or "")
    if not m:
        raise Mp4Error("No TikTok link found - paste a link like https://www.tiktok.com/@user/video/123...")
    return m.group(0).rstrip(".,)>]")


def _page_streams(session, url):
    resp = session.get(url)
    final = resp.geturl()
    html = resp.read().decode("utf-8", "replace")
    if "/photo/" in final:
        raise Mp4Error("This link is a photo post, not a video.")
    m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return final, None
    data = json.loads(m.group(1))
    detail = data.get("__DEFAULT_SCOPE__", {}).get("webapp.video-detail", {})
    item = detail.get("itemInfo", {}).get("itemStruct", {})
    video = item.get("video") or {}
    if not video:
        return final, None
    streams = []
    for b in video.get("bitrateInfo") or []:
        pa = b.get("PlayAddr") or {}
        w, h = pa.get("Width") or 0, pa.get("Height") or 0
        streams.append({
            "name": b.get("GearName") or "?",
            "fps": b.get("BitrateFPS") or 0,
            "width": w, "height": h,
            "codec": CODECS.get((b.get("CodecType") or "").lower(), b.get("CodecType") or "?"),
            "mbps": (b.get("Bitrate") or 0) / 1e6,
            "size": int(pa.get("DataSize") or 0),
            "urls": pa.get("UrlList") or [],
        })
    if not streams and video.get("playAddr"):
        streams.append({"name": "play", "fps": 0, "width": video.get("width") or 0,
                        "height": video.get("height") or 0, "codec": "?", "mbps": 0,
                        "size": 0, "urls": [video["playAddr"]]})
    return final, {
        "source": "tiktok",
        "author": (item.get("author") or {}).get("uniqueId", ""),
        "title": (item.get("desc") or "")[:80],
        "duration": video.get("duration") or 0,
        "width": video.get("width") or 0,
        "height": video.get("height") or 0,
        "vqscore": video.get("VQScore"),
        "streams": sorted(streams, key=lambda s: (s["fps"], s["height"], s["mbps"]), reverse=True),
    }


def _tikwm(session, url):
    body = urllib.parse.urlencode({"url": url, "hd": 1}).encode()
    resp = session.get("https://www.tikwm.com/api/", data=body, headers={"Accept": "application/json"})
    j = json.loads(resp.read())
    d = j.get("data") or {}
    if j.get("code") != 0 or not (d.get("hdplay") or d.get("play")):
        raise Mp4Error(f"Video not found ({j.get('msg') or 'private, deleted or region-locked'}).")
    streams = []
    for key, size_key in (("hdplay", "hd_size"), ("play", "size")):
        if d.get(key):
            streams.append({"name": key, "fps": 0, "width": 0, "height": 0, "codec": "?",
                            "mbps": 0, "size": int(d.get(size_key) or 0), "urls": [d[key]]})
    return {"source": "tikwm", "author": (d.get("author") or {}).get("unique_id", ""),
            "title": (d.get("title") or "")[:80], "duration": d.get("duration") or 0,
            "width": 0, "height": 0, "vqscore": None, "streams": streams}


def check(text):
    """Return (info dict, session). info['streams'] is sorted best-first."""
    url = extract_url(text)
    session = Session()
    info = None
    try:
        url, info = _page_streams(session, url)
    except Mp4Error:
        raise
    except Exception:
        info = None
    if not info or not info["streams"]:
        try:
            info = _tikwm(session, url)
        except Mp4Error:
            raise
        except Exception as e:
            raise Mp4Error(f"Could not read the video from TikTok or tikwm: {e}")
    info["url"] = url
    info["best_fps"] = max((s["fps"] for s in info["streams"]), default=0)
    return info, session


def download(info, session, dest, stream=None, progress=None, cancel=None):
    """Download a stream (default: best) to dest. Returns dest."""
    stream = stream or info["streams"][0]
    last = None
    for u in stream["urls"]:
        try:
            resp = session.get(u, headers={"Referer": "https://www.tiktok.com/"}, timeout=60)
            total = int(resp.headers.get("Content-Length") or stream["size"] or 0)
            done = 0
            with open(dest, "wb") as f:
                while True:
                    if cancel and cancel():
                        raise Mp4Error("Cancelled.")
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress and total:
                        progress(min(1.0, done / total))
            if done > 1024:
                return dest
        except Mp4Error:
            raise
        except Exception as e:
            last = e
    try:
        os.remove(dest)
    except OSError:
        pass
    raise Mp4Error(f"Download failed: {last or 'no working stream URL'}")


def verdict(best_fps):
    """'smooth' (>=50 fps), 'normal' (~30) or 'unknown'."""
    if not best_fps:
        return "unknown"
    return "smooth" if best_fps >= 50 else "normal"

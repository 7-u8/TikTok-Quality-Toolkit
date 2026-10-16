"""Minimal MP4/ISO-BMFF reader shared by all tools.

Top-level boxes are walked with file seeks (mdat is never loaded); the moov
box is loaded into memory and parsed from a buffer.
"""

import os
import struct
from collections import namedtuple


class Mp4Error(Exception):
    pass


class Box(namedtuple("Box", "type pos hlen size")):
    @property
    def body(self):
        return self.pos + self.hlen

    @property
    def end(self):
        return self.pos + self.size


def u8(buf, off):
    return buf[off]


def u16(buf, off):
    return struct.unpack_from(">H", buf, off)[0]


def u32(buf, off):
    return struct.unpack_from(">I", buf, off)[0]


def u64(buf, off):
    return struct.unpack_from(">Q", buf, off)[0]


def _box_at(size, typ, pos, hlen, end):
    if size < hlen or pos + size > end:
        raise Mp4Error(f"Not a valid MP4 (corrupt box at offset {pos}).")
    return Box(typ.decode("latin-1"), pos, hlen, size)


def file_boxes(f, start, end):
    """Yield top-level Boxes from an open file between start and end."""
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        size, typ = struct.unpack(">I4s", f.read(8))
        hlen = 8
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]
            hlen = 16
        elif size == 0:
            size = end - pos
        yield _box_at(size, typ, pos, hlen, end)
        pos += size


def children(buf, start, end):
    """Yield Boxes contained in buf[start:end]."""
    pos = start
    while pos + 8 <= end:
        size, typ = struct.unpack_from(">I4s", buf, pos)
        hlen = 8
        if size == 1:
            size = u64(buf, pos + 8)
            hlen = 16
        elif size == 0:
            size = end - pos
        yield _box_at(size, typ, pos, hlen, end)
        pos += size


def find(buf, parent, *path):
    """Follow a path of box types below parent (a Box). Returns Box or None."""
    box = parent
    for name in path:
        for child in children(buf, box.body, box.end):
            if child.type == name:
                box = child
                break
        else:
            return None
    return box


def find_all(buf, parent, name):
    return [c for c in children(buf, parent.body, parent.end) if c.type == name]


# ------------------------------------------------------------- header fields


def header_fields(buf, box):
    """Offsets of (timescale, duration, duration_size) in an mvhd/mdhd box."""
    ver = buf[box.body]
    if ver == 0:
        ts = box.body + 12
        return ts, ts + 4, 4
    if ver == 1:
        ts = box.body + 20
        return ts, ts + 4, 8
    raise Mp4Error(f"Unsupported '{box.type}' version {ver}.")


def read_timescale_duration(buf, box):
    ts_off, dur_off, dsz = header_fields(buf, box)
    dur = u32(buf, dur_off) if dsz == 4 else u64(buf, dur_off)
    return u32(buf, ts_off), dur


def tkhd_duration_field(buf, tkhd):
    ver = buf[tkhd.body]
    if ver == 0:
        return tkhd.body + 20, 4
    if ver == 1:
        return tkhd.body + 28, 8
    raise Mp4Error(f"Unsupported 'tkhd' version {ver}.")


def mdhd_language_offset(buf, mdhd):
    _, dur_off, dsz = header_fields(buf, mdhd)
    return dur_off + dsz


# --------------------------------------------------------------- sample tables


def parse_stts(buf, box):
    n = u32(buf, box.body + 4)
    return [struct.unpack_from(">II", buf, box.body + 8 + i * 8) for i in range(n)]


def parse_stsz(buf, box):
    uniform = u32(buf, box.body + 4)
    n = u32(buf, box.body + 8)
    if uniform:
        return [uniform] * n
    return list(struct.unpack_from(f">{n}I", buf, box.body + 12))


def parse_stsc(buf, box):
    n = u32(buf, box.body + 4)
    return [struct.unpack_from(">III", buf, box.body + 8 + i * 12) for i in range(n)]


def parse_stco(buf, box):
    n = u32(buf, box.body + 4)
    if box.type == "co64":
        return list(struct.unpack_from(f">{n}Q", buf, box.body + 8))
    return list(struct.unpack_from(f">{n}I", buf, box.body + 8))


def parse_elst(buf, box):
    """Return [(segment_duration, media_time), ...]."""
    ver = buf[box.body]
    n = u32(buf, box.body + 4)
    out = []
    pos = box.body + 8
    for _ in range(n):
        if ver == 1:
            dur, mt = struct.unpack_from(">Qq", buf, pos)
            pos += 20
        else:
            dur, mt = struct.unpack_from(">Ii", buf, pos)
            pos += 12
        out.append((dur, mt))
    return out


# ------------------------------------------------------------------ the file


class Track:
    def __init__(self, buf, trak):
        self.trak = trak
        self.tkhd = find(buf, trak, "tkhd")
        self.mdia = find(buf, trak, "mdia")
        if self.mdia is None:
            raise Mp4Error("Track without 'mdia' box.")
        self.mdhd = find(buf, self.mdia, "mdhd")
        self.hdlr = find(buf, self.mdia, "hdlr")
        self.handler = buf[self.hdlr.body + 8 : self.hdlr.body + 12].decode("latin-1") if self.hdlr else "?"
        self.timescale, self.duration = read_timescale_duration(buf, self.mdhd)
        self.stbl = find(buf, self.mdia, "minf", "stbl")
        self.codec = None
        self.stts = []
        self.sample_count = 0
        self.chunk_box = None
        if self.stbl is not None:
            stsd = find(buf, self.stbl, "stsd")
            if stsd is not None and u32(buf, stsd.body + 4) > 0:
                self.codec = buf[stsd.body + 12 : stsd.body + 16].decode("latin-1")
            stts = find(buf, self.stbl, "stts")
            if stts is not None:
                self.stts = parse_stts(buf, stts)
                self.sample_count = sum(c for c, _ in self.stts)
            self.chunk_box = find(buf, self.stbl, "stco") or find(buf, self.stbl, "co64")

    @property
    def fps(self):
        total = sum(c * d for c, d in self.stts)
        if not total or not self.timescale:
            return None
        return self.sample_count * self.timescale / total

    @property
    def header_fps(self):
        """Frames divided by the mdhd duration. Differs from `fps` when a
        file has already been FPS-patched or ghost-framed."""
        return self.sample_count / self.seconds if self.seconds else None

    @property
    def already_patched(self):
        a, b = self.fps, self.header_fps
        return bool(a and b) and max(a, b) / min(a, b) > 1.3

    @property
    def is_cfr(self):
        deltas = {d for _, d in self.stts[:-1]} if len(self.stts) > 1 else {d for _, d in self.stts}
        return len(deltas) <= 1

    @property
    def seconds(self):
        return self.duration / self.timescale if self.timescale else 0


class Mp4File:
    """Parsed layout of an MP4 file. `moov` is held in memory as `buf`;
    box positions inside it are relative to `buf`, add `moov_offset` for the
    absolute file offset."""

    def __init__(self, path):
        self.path = path
        self.file_size = os.path.getsize(path)
        self.top = []
        with open(path, "rb") as f:
            self.top = list(file_boxes(f, 0, self.file_size))
            moov = [b for b in self.top if b.type == "moov"]
            if not moov:
                raise Mp4Error("No 'moov' box found - this is not a valid MP4 file.")
            m = moov[0]
            f.seek(m.pos)
            self.buf = f.read(m.size)
        self.moov_offset = m.pos
        self.moov = Box("moov", 0, m.hlen, m.size)
        self.mvhd = find(self.buf, self.moov, "mvhd")
        if self.mvhd is None:
            raise Mp4Error("No 'mvhd' box found inside 'moov'.")
        self.movie_timescale, self.movie_duration = read_timescale_duration(self.buf, self.mvhd)
        self.tracks = [Track(self.buf, t) for t in find_all(self.buf, self.moov, "trak")]
        if not self.tracks:
            raise Mp4Error("No tracks found in the MP4.")

    def top_types(self):
        return [b.type for b in self.top]

    @property
    def fragmented(self):
        return "moof" in self.top_types() or find(self.buf, self.moov, "mvex") is not None

    @property
    def faststart(self):
        types = self.top_types()
        return "mdat" in types and types.index("moov") < types.index("mdat")

    def track(self, handler):
        for t in self.tracks:
            if t.handler == handler:
                return t
        return None

    @property
    def video(self):
        return self.track("vide")

    @property
    def audio(self):
        return self.track("soun")

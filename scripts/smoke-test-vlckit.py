#!/usr/bin/env python3
"""Decode a local synthetic H.264/AAC clip through the candidate Mac libVLC 4.

Uses memory audio/video callbacks: success requires decoded nonzero samples
and multiple video frames. Does not qualify provider streams or native UI.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import time


def smoke(binary, media):
    lib = C.CDLL(str(binary.resolve()))
    pointer = C.c_void_p
    def api(name, result, *arguments):
        f = getattr(lib, name)
        f.restype, f.argtypes = result, arguments
        return f
    new = api('libvlc_new', pointer, C.c_int, C.POINTER(C.c_char_p))
    release = api('libvlc_release', None, pointer)
    version = api('libvlc_get_version', C.c_char_p)
    changeset = api('libvlc_get_changeset', C.c_char_p)
    create_media = api('libvlc_media_new_path', pointer, C.c_char_p)
    release_media = api('libvlc_media_release', None, pointer)
    create_player = api('libvlc_media_player_new', pointer, pointer, pointer, pointer)
    release_player = api('libvlc_media_player_release', None, pointer)
    set_media = api('libvlc_media_player_set_media', None, pointer, pointer)
    play = api('libvlc_media_player_play', C.c_int, pointer)
    stop = api('libvlc_media_player_stop_async', C.c_int, pointer)
    get_state = api('libvlc_media_player_get_state', C.c_int, pointer)
    lock_type = C.CFUNCTYPE(pointer, pointer, C.POINTER(pointer))
    display_type = C.CFUNCTYPE(None, pointer, pointer)
    audio_type = C.CFUNCTYPE(None, pointer, pointer, C.c_uint, C.c_int64)
    set_video = api('libvlc_video_set_callbacks', None, pointer, lock_type, pointer, display_type, pointer)
    format_video = api('libvlc_video_set_format', None, pointer, C.c_char_p, C.c_uint, C.c_uint, C.c_uint)
    set_audio = api('libvlc_audio_set_callbacks', None, pointer, audio_type, pointer, pointer, pointer, pointer, pointer)
    format_audio = api('libvlc_audio_set_format', None, pointer, C.c_char_p, C.c_uint, C.c_uint)
    frame = C.create_string_buffer(320 * 180 * 4)
    counts = {'video_frames': 0, 'audio_frames': 0, 'nonzero_video': False, 'nonzero_audio': False}
    @lock_type
    def lock(opaque, planes):
        planes[0] = C.addressof(frame)
        return C.addressof(frame)
    @display_type
    def display(opaque, picture):
        counts['video_frames'] += 1
        counts['nonzero_video'] |= any(frame.raw)
    @audio_type
    def audio(opaque, samples, count, pts):
        counts['audio_frames'] += count
        counts['nonzero_audio'] |= any(C.string_at(samples, count * 4))
    options = [b'--no-video-title-show', b'--no-osd', b'--quiet']
    instance = new(len(options), (C.c_char_p * len(options))(*options))
    if not instance:
        raise RuntimeError('libvlc_new failed')
    player = media_object = None
    try:
        media_object = create_media(str(media.resolve()).encode())
        player = create_player(instance, None, None)
        if not player or not media_object:
            raise RuntimeError('media/player creation failed')
        set_media(player, media_object)
        set_video(player, lock, None, display, None)
        format_video(player, b'RV32', 320, 180, 1280)
        set_audio(player, audio, None, None, None, None, None)
        format_audio(player, b'S16N', 48000, 2)
        if play(player) != 0:
            raise RuntimeError('play request failed')
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            state = get_state(player)
            if state == 6:
                raise RuntimeError('player entered libvlc_Error')
            if state == 4 and counts['video_frames']:
                break
            time.sleep(.05)
        else:
            raise RuntimeError('playback did not finish within 15 seconds')
        if counts['video_frames'] < 25 or counts['audio_frames'] < 48000 or not all(
            counts[key] for key in ('nonzero_video', 'nonzero_audio')):
            raise RuntimeError('insufficient decoded audio/video: ' + str(counts))
        return {'status': 'PASSED_SYNTHETIC_H264_AAC', 'runtime_version': version().decode(),
                'runtime_changeset': changeset().decode(),
                'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                'media_sha256': hashlib.sha256(media.read_bytes()).hexdigest(), **counts}
    finally:
        if player:
            stop(player)
            deadline = time.monotonic() + 5
            while get_state(player) == 5 and time.monotonic() < deadline:
                time.sleep(.05)
            release_player(player)
        if media_object:
            release_media(media_object)
        release(instance)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--media', type=Path, required=True)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    report = smoke(args.binary, args.media)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()

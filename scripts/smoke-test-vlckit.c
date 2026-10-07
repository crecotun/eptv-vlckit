/* Decode an owned synthetic H.264/AAC clip through a tvOS Simulator framework.
 * Used only by the dependency qualification workflow; no provider input. */
#include <vlc/vlc.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static unsigned char frame[320 * 180 * 4];
static atomic_uint video_frames, audio_frames;
static atomic_bool nonzero_video, nonzero_audio;

static void *lock_video(void *opaque, void **planes)
{
    (void)opaque;
    planes[0] = frame;
    return frame;
}
static void display_video(void *opaque, void *picture)
{
    (void)opaque; (void)picture;
    atomic_fetch_add(&video_frames, 1);
    for (size_t i = 0; i < sizeof(frame); i++) {
        if (frame[i]) { atomic_store(&nonzero_video, true); break; }
    }
}
static void play_audio(void *opaque, const void *samples, unsigned count, int64_t pts)
{
    (void)opaque; (void)pts;
    atomic_fetch_add(&audio_frames, count);
    const unsigned char *bytes = samples;
    for (size_t i = 0; i < count * 4; i++) {
        if (bytes[i]) { atomic_store(&nonzero_audio, true); break; }
    }
}
int main(int argc, char **argv)
{
    if (argc != 2) return 64;
    const char *options[] = { "--no-video-title-show", "--no-osd", "--quiet" };
    libvlc_instance_t *instance = libvlc_new(3, options);
    if (!instance) return 1;
    libvlc_media_t *media = libvlc_media_new_path(argv[1]);
    libvlc_media_player_t *player = libvlc_media_player_new(instance, NULL, NULL);
    if (!media || !player) return 2;
    libvlc_media_player_set_media(player, media);
    libvlc_video_set_callbacks(player, lock_video, NULL, display_video, NULL);
    libvlc_video_set_format(player, "RV32", 320, 180, 1280);
    libvlc_audio_set_callbacks(player, play_audio, NULL, NULL, NULL, NULL, NULL);
    libvlc_audio_set_format(player, "S16N", 48000, 2);
    if (libvlc_media_player_play(player)) return 3;
    bool ended = false;
    for (unsigned i = 0; i < 300; i++) {
        libvlc_state_t state = libvlc_media_player_get_state(player);
        if (state == libvlc_Error) return 4;
        if (state == libvlc_Stopped && atomic_load(&video_frames)) { ended = true; break; }
        usleep(50000);
    }
    unsigned video = atomic_load(&video_frames), audio = atomic_load(&audio_frames);
    bool decoded = ended && video >= 25 && audio >= 48000 &&
                   atomic_load(&nonzero_video) && atomic_load(&nonzero_audio);
    printf("{\"status\":\"%s\",\"runtime_changeset\":\"%s\",\"video_frames\":%u,\"audio_frames\":%u}\n",
           decoded ? "PASSED_SYNTHETIC_H264_AAC" : "FAILED", libvlc_get_changeset(), video, audio);
    libvlc_media_player_stop_async(player);
    libvlc_media_player_release(player);
    libvlc_media_release(media);
    libvlc_release(instance);
    return decoded ? 0 : 5;
}

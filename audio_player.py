import subprocess, sys
import threading, time
from enum import Enum
from pydub import AudioSegment
from djutils import logit
import sounddevice as sd
import numpy as np

class PlayerState(Enum):
    STOPPED = 1
    PAUSED = 2
    PLAYING = 3

class UpdaterThread(threading.Thread):
    def __init__(self, root):
        super(UpdaterThread, self).__init__(daemon=True)
        self.root = root
        self.remaining = 0
        self.stop_event = threading.Event()
        self.start_event = threading.Event()

    def start_countdown(self, time_seconds):
        self.remaining = time_seconds
        self.stop_event.clear()
        self.start_event.set()

    def run(self):
        while True:
            self.start_event.wait()
            while self.remaining > 1 and not self.stop_event.is_set():
                self.remaining = self.remaining - 1
                m = int(self.remaining // 60)
                s = int(self.remaining % 60)
                self.root.set_countdown(f"{m:02}:{s:02}")
                time.sleep(1)

            self.root.set_title("")
            self.start_event.clear()

            
class PlayerThread(threading.Thread):
    def __init__(self, parent, sd):
        super(PlayerThread, self).__init__(daemon=True)
        self.parent = parent
        self.track = None
        self.sd = sd
        self.state = PlayerState.STOPPED
        self.start_playback = threading.Event()
        self.updater = UpdaterThread(self.parent)
        self.updater.start()

    def is_playing(self):
        return self.state == PlayerState.PLAYING

    def is_stopped(self):
        return self.state == PlayerState.STOPPED

    def stop_player(self):
        self.state = PlayerState.STOPPED

    def start_player(self, track):
        logit(f"start_player {track.title}")
        if self.state == PlayerState.PLAYING:
            self.state = PlayerState.STOPPED
            time.sleep(1)
            
        self.track = track
        self.start_playback.set()


    def run(self):
        while True:
            self.start_playback.wait()
            self.play_audio()

    def play_audio(self):
        samplerate = 48000
        channels = 2
        block_size = 4096

        self.start_playback.clear()
        self.state = PlayerState.PLAYING
        device_index = self.parent._get_selected_device_index()

        ffmpeg_flags = 0
        if sys.platform == "win32":
            ffmpeg_flags = subprocess.CREATE_NO_WINDOW

        while self.is_playing() and self.track:
            try:
                self.parent.prepare_track_for_playback(self.track)
                if self.track.is_stop_file():
                    break

                ffmpeg_process = subprocess.Popen(
                    [
                        "ffmpeg",
                        "-loglevel", "error",
                        "-probesize", "32k",
                        "-analyzeduration", "0",
                        "-i", self.track.file_path,
                        "-f", "f32le",
                        "-acodec", "pcm_f32le",
                        "-ac", str(channels),
                        "-ar", str(samplerate),
                        "-"
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=10**6,
                    creationflags=ffmpeg_flags
                )
            
                stream = self.sd.OutputStream(
                    samplerate=samplerate,
                    channels=channels,
                    dtype='float32',
                    blocksize=block_size,
                    device=device_index
                )
            
                bytes_per_frame = channels * 4
                self.updater.start_countdown(self.track.duration)

                with stream:
                    while self.is_playing():
                        data = ffmpeg_process.stdout.read(block_size * bytes_per_frame)
            
                        if not data:
                            if ffmpeg_process.poll() is not None:
                                err = ffmpeg_process.stderr.read().decode()
                                if err:
                                    print("FFmpeg error:", err)
                                break
                            continue
            
                        audio = np.frombuffer(data, dtype=np.float32).reshape(-1, channels)
                        stream.write(audio)

                self.updater.stop_event.set()
                stream.close()
            except Exception as ex:
                logit(f"Playback error: {ex}")

            if self.is_playing():
                self.track = self.parent.get_next_track_for_playback(self.track.id)
        
        self.state = PlayerState.STOPPED


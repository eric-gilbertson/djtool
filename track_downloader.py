# asynchromously downloads a track using yt-dlp and performs name cleanup on the downloaded file.
#
import io, glob, traceback
import logging
import platform, urllib, stat, ssl, certifi
import threading, subprocess, shutil, re, os, zipfile
from datetime import datetime
from pathlib import Path
from tkinter import simpledialog
import tkinter as tk
from tkinter import messagebox

from ytmusicapi import YTMusic
from fuzzy_search import FuzzyYTMusic
from yt_dlp import YoutubeDL

from audio_trimmer import trim_audio
from models import Track
from djutils import logit
from system_config import SystemConfig

FIELD_SEPARATOR = '^'

# downloads using the python library
class YTDLPThread(threading.Thread):
    def __init__(self, file_prefix, out_file, track_url, done_callback, audio_format, is_playlist, ffmpeg_path):
        super(YTDLPThread, self).__init__()
        self.done_callback = done_callback
        self.out_file = out_file
        self.file_prefix = file_prefix
        self.track_url = track_url
        self.is_playlist = is_playlist
        self.audio_format = audio_format
        self.ffmpeg_path = ffmpeg_path

    def run(self):
        try:
            output_buffer = io.StringIO()
            logger = logging.getLogger('yt_dlp_logger')
            logger.setLevel(logging.DEBUG)
    
            # 2. Add a handler that writes to the buffer
            handler = logging.StreamHandler(output_buffer)
            logger.addHandler(handler)
            # TODO: add ffmpeg_path
            ydl_opts = {
                'logger': logger,
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': self.out_file,
                'quiet': True,
                'ffmpeg_location' : self.ffmpeg_path,
#                'cookiesfrombrowser': ('chrome',),
            }

            # throttle downloads so we aren't flagged as an abuser
            if self.is_playlist:
                ydl_opts['sleep_interval'] = 5
                ydl_opts['max_sleep_interval'] = 10

            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',  # Correct key is essential
                'preferredcodec': self.audio_format,
            }]
    
            with YoutubeDL(ydl_opts) as ydl:
                status = ydl.download([self.track_url])
                logit(f"download status: {status}")
    
            #NOTE: string extraction can throw an execption on Windows because the string can
            # contain binary data that it can't decode.
            stdout = output_buffer.getvalue()
            self.done_callback(status, self.file_prefix, stdout)
        except Exception as ex:
            ret_msg = f"An exception occurred during download {ex} \n\n{traceback.format_exc()}"
            logit(ret_msg)
            self.done_callback(1, self.file_prefix, ret_msg)

# downloads using external yt-dlp binary
class CommandThread(threading.Thread):
    def __init__(self, file_prefix, cmd, done_callback):
        super(CommandThread, self).__init__()
        self.done_callback = done_callback
        self.cmd = cmd
        self.file_prefix = file_prefix

    def run(self):
        try:
            process = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            (stdout, stderr) = process.communicate()
            # merging them because that's what the API versiond does.
            ret_msg = stderr.decode('UTF-8') + "\n" +stdout.decode('UTF-8')
            self.done_callback(process.returncode, self.file_prefix, ret_msg)
        except Exception as ex:
            ret_msg = f"An error occurred during download {ex}"
            logit(ret_msg)
            self.done_callback(1, self.file_prefix, ret_msg)


class TrackDownloader():
    YTDL_ALT_PATH_MACOS = os.path.expanduser("~") + "/Library/yt-dlp_macos/yt-dlp_macos"
    AUDIO_FORMAT = "opus"
    YTDWNLD_PREFIX = 'YTDLPDWNLD-'
    YTDWNLD_PREFIX_END_CHAR = '_'
     
    def __init__(self, parent, download_dir, ffmpeg_path):
        self.FFMPEG_PATH = ffmpeg_path

        # use user installed verion if available, else use bundled version if availabe.
        self.YTDL_PATH = shutil.which('yt-dlp')
        if not self.YTDL_PATH and platform.system() == 'Darwin' and os.path.exists(self.YTDL_ALT_PATH_MACOS):
            self.YTDL_PATH = self.YTDL_ALT_PATH_MACOS

        logit(f"yt-dlp path: -{self.YTDL_PATH}-")
        self.download_dir = download_dir
        self.parent = parent
        self.download_thread = None
        self.name_too_long = False
        self.err_msg = ''
        self.track = Track()
        self.tracks = []
        self.track_url = ''
        self.is_done = False
        self.fuzzy_search = FuzzyYTMusic()


        if not os.path.exists(download_dir):
            os.makedirs(download_dir)


    def update_ytdlp(self):
        logit("Start yt-dlp update")

        # only checking on Mac because the Windows version of yt-dlp.exe does
        # not require Python.
        message = "UNKNOWN"
        if platform.system() == 'Darwin' and not self.YTDL_PATH:
            doit = tk.messagebox.askokcancel(title="Info", message='The yt-dlp downloader application was not found. Would you like to install it now (this will take around 30 seconds to complete)? Alternatively, you can install it manually per the instructions in the Vew->Help page.', parent=self.parent)
            if doit:
                version = self.install_ytdlp_macos(self.YTDL_ALT_PATH_MACOS)
                if version:
                    message = f"Yt-dlp {version} was installed at {self.YTDL_ALT_PATH_MACOS}"
                    self.YTDL_PATH = self.YTDL_ALT_PATH_MACOS
                else:
                    title = "Error"
                    message='Yt-dlp was not installed. See the log using View->Log file for more informaton.'
            else:
                return
        elif not os.path.exists(self.YTDL_PATH):
            message =  f"Yt-dlp path: {self.YTDL_PATH} is invalid. Please reinstall it."
        else:
            result = subprocess.run([self.YTDL_PATH, "-U"], capture_output=True, text=True)
            message =  str(result.stdout)

        tk.messagebox.showwarning(title="Yt-dlp Status", message=message)

    def install_ytdlp_macos(self, install_path):
        try:
            install_dir = str(Path(self.YTDL_ALT_PATH_MACOS).parent)
            if os.path.exists(install_dir):
                shutil.rmtree(install_dir)

            os.mkdir(install_dir)
            
            url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos.zip"
            context = ssl.create_default_context(cafile=certifi.where())
            ssl._create_default_https_context = lambda: context
            zip_path = f"{install_dir}/yt-dlp_macos.zip"
            urllib.request.urlretrieve(url, zip_path)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(install_dir)

            current_mode = os.stat(install_path).st_mode
            os.chmod(install_path, current_mode | stat.S_IXUSR)

            result = subprocess.run([install_path, "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                os.remove(zip_path)
                return str(result.stdout)
        except Exception as ex:
            logit(f"Error installing yt-dlp_macos: {ex}")

        return False

    @staticmethod
    def check_dependencies():
        msg = None
    
        if not SystemConfig.user_apikey:
            message=f'Live show updating is not available because your User API Key has not been set. Enter your administrator supplied apikey using the File->Configuration dialog. See View->Help for setup help information.'
            tk.messagebox.showwarning(title='Incomplete Setup', message=message)
        elif not SystemConfig.spotify_id or not SystemConfig.spotify_secret:
            msg = '''Spotify features are not available because the Spotify apikeys have not been set. Check that your user key in the File->Configuration dialog matches the api key at https://kzsu.stanford.edu/internal/profile'''
    
            tk.messagebox.showwarning("Configuration Error", msg)
        elif not SystemConfig.genius_apikey:
            msg = '''The FCC check feature is not available because the Genius apikey has not been set. Check that your user key in the File->Configuration dialog matches the api key at https://kzsu.stanford.edu/internal/profile'''
    
            tk.messagebox.showwarning("Configuration Error", msg)

    def fetch_track(self, parent, track_specifier, use_fullname):
        logit(f"Enter fetch_track: {track_specifier}")
        if not self.FFMPEG_PATH:
            tk.messagebox.showwarning(title="Error", message="FFMPEG was not found and it is required to download songs. Please install it and try again.", parent=self.parent)
            return False

        is_url = 'https:/' in track_specifier
        ARTIST_TRACK_SEPARATOR = r' - |;|\t| – ' # split on -, ; and <tab>
        artistTerm = '%(artist)s' if use_fullname  else 'UNKNOWN'
        self.tracks.clear()
        self.track.reset()
        track_specifier_ar = re.split(ARTIST_TRACK_SEPARATOR, track_specifier)
        error_msg = '''Invalid song request. Enter either <ARTIST_NAME><SEPERATOR><SONG_TITLE> using -, ; or <TAB> as the artist/title separator or a YouTube song URL. Note that the artist and song values do not have to be complete, e.g. "Stones ; Satisfaction"  and that one of the values may be empty, e.g. use "Beatles;" to locate Beatles songs or ";Hallelujah" to find cover versions of that song. All entry values correctly spelled.'''
        
        if not is_url and len(track_specifier_ar) <  2:
            tk.messagebox.showwarning(title="Error", message=error_msg, parent=self.parent)
            return False

        # use_fullname is false when the first try fails because the artist name was too long
        # for the filename. if a second try then skip the track lookup and use the previous URL.
        if not is_url and use_fullname  and len(track_specifier_ar) == 2:
            artist = track_specifier_ar[0]
            title = track_specifier_ar[1]
            search_tracks = self.fuzzy_search.search_song(artist, title)
            if not search_tracks or len(search_tracks) == 0:
                msg = f"Nothing found for -{title}- by -{artist}-. Note that the format for song lookup is <ARTIST>;<TITLE>. The names do not have to be complete but they must be spelled correctly."
                tk.messagebox.showwarning(title="Error", message=msg)
                return False
            else:
                dialog = SelectTrackDialog(parent, artist, title, search_tracks)
                if not dialog.ok_clicked or len(dialog.track.id) == 0:
                    return False

                self.track.album = dialog.track.album
                self.track.artist = dialog.track.artist
                self.track.title = dialog.track.title
                self.track_url = f"https://youtube.com/watch?v={dialog.track.id}"
        elif use_fullname:
            self.track_url = track_specifier

        is_watch = "youtube.com/watch?" in self.track_url
        is_playlist = "youtube.com/playlist?" in self.track_url
        if not (is_watch or is_playlist):
            tk.messagebox.showwarning(title="Error", message=error_msg, parent=self.parent)
            return False

        # watch is followed by playlist then remove the latter so that only one song is downloaded
        if is_watch and (list_idx := self.track_url.find('&list=')) > 0:
            self.track_url = self.track_url[0:list_idx]

        if is_playlist:
            msg = "This URL is for a playlist. Are you sure that you want to download the entire playlist?"
            if not tk.messagebox.askokcancel(title="Confirm Operation", message=msg, parent=self.parent):
                return False

        logit(f"start song download")
        self.parent.after(0, self.parent.set_cursor('clock'))
        self.is_done = False

        # give a unique prefix that can be used to identify the downloaded file. was getting from
        # ytdlp's stdout but there were cases where file path characeters were lost on the byte
        # to string conversion on Windoze.
        file_prefix = self.YTDWNLD_PREFIX + datetime.now().strftime('%Y-%m-%dT%H%M%S') + self.YTDWNLD_PREFIX_END_CHAR
        dwnld_path = f"{self.download_dir}/{file_prefix}"
        throttle_option = ' --sleep-interval 5 --max-sleep-interval 10 ' if is_playlist else ''
        if self.YTDL_PATH:
            # passing in ffmpeg location because it may not be in the user's PATH
            out_file = f'"{dwnld_path}{artistTerm}_%(title)s.%(ext)s"'
            cmd = f'{self.YTDL_PATH} {throttle_option} --ffmpeg-location {self.FFMPEG_PATH} --extract-audio --audio-format {self.AUDIO_FORMAT}  -o {out_file} "{self.track_url}"'
            logit(f"Start external download: {cmd}")
            self.download_thread = CommandThread(dwnld_path, cmd, self.on_fetch_done)
            self.download_thread.start()
        else:
            # NOTE: no ext here, the extension will be set by the library
            out_file = f'{dwnld_path}{artistTerm}_%(title)s'
            logit(f"Start internal download: {self.track_url}, {out_file}")
            self.download_thread = YTDLPThread(dwnld_path, out_file, self.track_url, self.on_fetch_done, self.AUDIO_FORMAT, is_playlist, self.FFMPEG_PATH)
            self.parent.after(0, self.download_thread.start)
            #self.download_thread.start()

        return True

    def on_fetch_done(self, returnCode, dwnld_prefix, stdOut):
        self.err_msg = ''
        if stdOut.find('File name too long') > 0:
            self.name_too_long = True
        elif returnCode != 0:
            self.err_msg = f"yt-dlp download error: {stdOut}"
        else:
            new_files = glob.glob(f"{dwnld_prefix}*")
            for new_file in new_files:
                logit(f"Downloaded file: {new_file}")
                (file_path, file_artist, file_title) = self.clean_filepath(new_file)
                trim_audio(file_path)
                # use the title/artist from the downloaded iff it has not already been set.
                artist = self.track.artist if self.track.artist else file_artist
                title = self.track.title if self.track.title else file_title
                track = Track(1, '', '', artist, title, self.track.album,  '', file_path, 0)
                self.tracks.append(track)

        self.is_done = True


    # normalizes files downloaded from YT & MPE into standard <ARTIST>^<TITLE> name format.
    @staticmethod
    def clean_filepath(filepath):
        new_name_ext = os.path.basename(filepath)
        new_name, name_extension = os.path.splitext(new_name_ext)
        if new_name.startswith(TrackDownloader.YTDWNLD_PREFIX):
            new_name = new_name[new_name.find(TrackDownloader.YTDWNLD_PREFIX_END_CHAR) + 1:]

    
        if not filepath.endswith(('.wav', ".mp3", ".opus")):
            logit(f"Unexpected download file type: {filepath}")
            return (filepath, '', '')
    
        # remove parenthetical and bracketed text
        new_name = re.sub(r"[\(\[\{].*?[\)\]\}]", "", new_name)
        new_name = re.sub(r'- \d+ -', FIELD_SEPARATOR, new_name)

        # replace quoted song with seperator, e.g. John Craige "Judias"
        WIERD_QUOTE = '＂'
        if new_name.find(WIERD_QUOTE) > 0:
            new_name = new_name.replace(WIERD_QUOTE, FIELD_SEPARATOR, 1)
            new_name = new_name.replace(WIERD_QUOTE, '', 1)
    
        if new_name.find('Official Track') >= 0:
            new_name = new_name.replace('Official Track', '')
    
        if new_name.find('Official Lyric Video') >= 0:
            new_name = new_name.replace('Official Lyric Video', '')
    
        if new_name.find('Lyric Video') >= 0:
            new_name = new_name.replace('Lyric Video', '')
    
        if new_name.find('OFFICIAL MUSIC VIDEO') >= 0:
            new_name = new_name.replace('OFFICIAL MUSIC VIDEO', '')
    
        if new_name.find('NA_') >= 0:
            new_name = new_name.replace('NA_', '')
    
        if new_name.find('｜') >= 0:
            new_name = new_name.replace('｜', FIELD_SEPARATOR)
    
        if new_name.find(' : ') >= 0:
            new_name = new_name.replace(' : ', FIELD_SEPARATOR)
    
        if new_name.find('＂') >= 0:  # special fat double quote from &quot; in html
            new_name = new_name.replace('＂', '')
    
        if new_name.find('"') >= 0:  # regular double quote
            new_name = new_name.replace('"', '')
    
        if new_name.find('-') >= 0:
            new_name = new_name.replace('-', FIELD_SEPARATOR)
    
        if new_name.find('_') >= 0:
            new_name = new_name.replace('_', ' ' + FIELD_SEPARATOR + ' ')
    
        if new_name.find('–') >= 0:
            new_name = new_name.replace('–', FIELD_SEPARATOR)
    
        if new_name.find('Official HD Audio') >= 0:  # regular double quote
            new_name = new_name.replace(' Official HD Audio', '')
    
        if new_name.find('Official Music Video') >= 0:  # regular double quote
            new_name = new_name.replace(' Official Music Video', '')
    
        if new_name.find(f"{FIELD_SEPARATOR} {FIELD_SEPARATOR}") >= 0:
            new_name = new_name.replace(f"{FIELD_SEPARATOR} {FIELD_SEPARATOR}", FIELD_SEPARATOR)
    
        if new_name.find(f"{FIELD_SEPARATOR} .") >= 0:
            new_name = new_name.replace(f"{FIELD_SEPARATOR} .", ".")
    
        namesAr = new_name.split(FIELD_SEPARATOR)
        commaIdx = namesAr[0].find(',')
        artist = namesAr[0].strip() if commaIdx < 0 else namesAr[0][0:commaIdx].strip()
        title = os.path.splitext(namesAr[1])[0].strip() if len(namesAr) > 1 else ''
        new_file = f"{os.path.dirname(filepath)}/{new_name}{name_extension}"

        if new_file != filepath:
            if os.path.exists(new_file):
                os.remove(new_file) # needed for Windoze

            os.replace(filepath, new_file)
    
        Path(new_file).touch()
        return (new_file, artist, title)

    def edit_track(self, parent, track):
        dialog = TrackEditDialog(parent, "Edit Track",
                                 track.artist,
                                 track.title,
                                 track.album)

        if dialog.ok_clicked:
            #self.is_dirty = True
            track.artist = dialog.track_artist
            track.title = dialog.track_title
            track.album = dialog.track_album
            unused, suffix = os.path.splitext(track.file_path)

            new_file = f"{os.path.dirname(track.file_path)}/{track.artist} {FIELD_SEPARATOR} {track.title}{suffix}"
            os.replace(track.file_path, new_file)
            track.file_path = new_file

            #row_values = self.tree.item(track.id)["values"]
            #row_values = (*row_values[0:2], track.artist, track.title, track.album)
            #self.tree.item(track.id, values=row_values)
            return True
        else:
            return False


class SelectTrackDialog(simpledialog.Dialog):
    def __init__(self, parent, track_artist, track_title, track_choices):
        # store initial values
        self.track_choices = track_choices
        self.ok_clicked = False

        self.track = Track()
        self.track.title = track_title
        self.track.artist = track_artist
        self.track.album = ''
        self.parent = parent
        super().__init__(parent, title='Select Song')

    def body(self, master):
        self.choices_entry = tk.Text(master, borderwidth=1, relief="solid", width=80)
        self.choices_entry.bind("<Double-1>", lambda e: self._select_row(e))
        self.choices_entry.config(cursor="arrow")

        self.choice_entry = tk.Entry(master, width=60)
        self.track_info = tk.Entry(master, width=60)

        idx = 1
        tracks = ''
        for track in self.track_choices:
            if track: # somehow got here if a None track so add this protection
                tracks = tracks + f"{idx}: {track['duration']} {track['title']} - {track['artists'][0]['name']} - {track['album']['name']}\n"
                idx = idx + 1

        self.choices_entry.insert("1.0", tracks)
        self.track_info.insert(0, f'{self.track.artist} - {self.track.title}')

        if idx > 1:
            self.choice_entry.insert(0, '1')

        self.choice_entry.focus_set()
 
        # Place widgets
        self.track_info.grid(row=1, column=0, padx=0, pady=5)
        self.choices_entry.grid(row=2, column=0, padx=0, pady=5)
        self.choice_entry.grid(row=3, column=0, padx=5, pady=5)

    def apply(self):
        # When Save is clicked
        self.ok_clicked = True

        choice = self.choice_entry.get()
        if len(choice) == 0:
            self.ok_clicked = False
        else:
            choice_num = int(choice) - 1
            track = self.track_choices[choice_num]
            self.track.id = track['videoId']
            self.track.album = track['album']['name']
            self.track.title = track['title']

            # often YT incorrectly assigns album as the title
#            if self.track.album  == self.track.title:
#                self.track.album = ''

            artists = ''
            seperator = ''
            for artist in track['artists']:
                artists = f'{artists}{seperator}{artist['name']}'
                seperator = ', '
            self.track.artist = artists
            self.on_close()


    def _select_row(self, event):
        index = self.choices_entry.index(f"@{event.x},{event.y}")
        line_number = int(index.split('.')[0]) - 1
        if line_number >= len(self.track_choices):
            return

        self.choice_entry.delete(0, tk.END)
        self.choice_entry.insert(0, str(line_number+1))
        self.ok()

    def on_close(self):
        logit("dialog destroy")
        self.grab_release() # Release grab before destroying
        self.destroy()
        self.parent.after(0, self.parent.set_cursor('clock'))


class TrackEditDialog(simpledialog.Dialog):
    def __init__(self, parent, hdr_title=None, track_artist="", track_title="", track_album=""):

        # store initial values
        self.initial_artist = track_artist
        self.initial_title = track_title
        self.initial_album = track_album
        self.ok_clicked = False
        self.track_artist = ""
        self.track_title  = ""
        self.track_album = ""
        super().__init__(parent, hdr_title)

    def body(self, master):
        #self.transient(master)  # stay on top of parent
        #self.grab_set_global()              # capture all events to this dialog

        # Create labels
        tk.Label(master, text="Artist:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text="Title:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text="Album:").grid(row=2, column=0, sticky="e", padx=5, pady=5)

        # Create entry fields with initial values
        self.artist_entry = tk.Entry(master, width=40)
        self.artist_entry.insert(0, self.initial_artist)

        self.title_entry = tk.Entry(master, width=40)
        self.title_entry.insert(0, self.initial_title)

        self.album_entry = tk.Entry(master, width=40)
        self.album_entry.insert(0, self.initial_album)

        # Place widgets
        self.artist_entry.grid(row=0, column=1, padx=5, pady=5)
        self.title_entry.grid(row=1, column=1, padx=5, pady=5)
        self.album_entry.grid(row=2, column=1, padx=5, pady=5)

        return self.artist_entry  # focus on artist field by default

    def apply(self):
        # When Save is clicked
        self.ok_clicked = True
        self.track_artist = self.artist_entry.get()
        self.track_title = self.title_entry.get()
        self.track_album = self.album_entry.get()


def getTitlesYouTube(artist, track):
    yt = YTMusic()
            
    if track.endswith((".mp3", ".wav", ".opus")):
        idx = 5 if track.endswith(".opus") else 4
        track = track[0:-idx]
        
    search_key = '"' + artist + '" "' + track + '"'
    
    # search types: songs, videos, albums, artists, playlists, community_playlists, featured_playlists, uploads
    search_results = yt.search(search_key, "albums")
    
    choices =[] 
    releases = []
    artist_lc = artist.lower()
    releaseTitle = None
    singleTitle = None
    for item in search_results:
        artists = ''
        for artist_row in item.get('artists', []):
            artists = artist_row['name'] + ', '
    
        if artists.lower().find(artist_lc) >= 0:
            releaseTitle = item['title']
            #key = '{} -\t {}'.format(artists, releaseTitle)
            if releaseTitle not in releases:
                choices.append(releaseTitle)
                releases.append(releaseTitle)

    if len(choices) == 0:
        logit(f"YouTube search for {track} by {artist} found {len(choices)} items")

    return choices


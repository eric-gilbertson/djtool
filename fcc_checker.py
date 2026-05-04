import re, urllib, ssl, json
from collections import Counter
from system_config import SystemConfig
import sys
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import lyricsgenius
from djutils import logit
from tkinter import messagebox

# test cases:
# dylan ; hurricane (shit, nigga
# pink floyd ; money (bull shit)
# james mcmurtry ; can't make it here (shit)
# Orville Peck & Margo Price - You're an Asshole (asshole,)
# julia king - insomnia (check correct author)
# Don Williams - Leaving Louisiana in Broad Daylight (rodnney crowell)
# Zach Bryan - Bad News (motherfucker)
# steven stills - season of the witch (donovan)
# Radiohead - creep (fuckin')
# Congress of Wonders - Star Trip (Genius)

class FCCChecker():
    SSL_CONTEXT = ssl._create_unverified_context()

    FCC_CLEAN = 'CLEAN'
    FCC_DIRTY = 'DIRTY'
    FCC_NOT_FOUND = 'NOT_FOUND'
    FCC_UNKNOWN = '-'
    FCC_STATUS_AR = [FCC_CLEAN, FCC_DIRTY, FCC_NOT_FOUND, FCC_UNKNOWN]

    #NOTE: artist should be primary artist & title should be title only, e.g. not ft....
    def __init__(self, artist, title):
        super().__init__()
        self.artist = artist
        self.title = title
        self.label = None
        self.album = None
        self.song_url = None
        self.fcc_status = self.FCC_NOT_FOUND
        self.explicit_msg = ''
        self.explicit_check()

    # requires spotify premium account
    def get_album_label(self, artist_name, album_name):
        have_keys = SystemConfig.spotify_id and SystemConfig.spotify_secret
    
        if not have_keys or not album_name or len(album_name) == 1:
            return ''
    
        album_label = ''
        try:
            spotify = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    client_id = SystemConfig.spotify_id,
                    client_secret= SystemConfig.spotify_secret
                )
            )
    
            results = spotify.search(q=f'album:{album_name} artist:{artist_name}', type='album', limit=1)
            if not results["albums"] or not results["albums"]["items"]:
                return None
    
            item = results['albums']["items"][0]
            album_id = item['id']
            album_info = spotify.album(album_id)
            album_label = album_info['label']
    
        except Exception as ex:
            logit(f"Exception getting album label from spotify {ex}")
    
        return album_label
    
    # requires spotify premium account
    def get_spotify_info(self, artist, title):
        is_explicit = None
        if not SystemConfig.spotify_id or not SystemConfig.spotify_secret:
            return None
    
        try:
            spotify = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    client_id = SystemConfig.spotify_id, 
                    client_secret= SystemConfig.spotify_secret
                )
            )
        
            # Search Spotify to normalize artist/title
            query = f"track:{title} artist:{artist}"
            results = spotify.search(q=query, type="track", limit=1)
        
            if not results["tracks"]["items"]:
                return None
        
            track = results["tracks"]["items"][0]
            normalized_title = track["name"]
            normalized_artist = track["artists"][0]["name"]
            is_explicit = track['explicit']
        except Exception as ex:
            logit(f"Exception getting album explicit from spotify {ex}")
    
        return is_explicit
    
        
    def confirm_song_match(self, found_artist):
        msg = f"FCC check found lyrics for {self.title} by {found_artist} instead of {self.artist}. Is this the same song?"
        return messagebox.askyesno("Confirm Lyrics", msg)

    def get_lyrics_genius(self):
        url = lyrics = album =None
        if not SystemConfig.genius_apikey:
            logit("Skipping genius check, api key not set")
            return (None, None, None)
    
        try:
            genius = lyricsgenius.Genius(SystemConfig.genius_apikey, skip_non_songs=True, remove_section_headers=True)
            artist_lc = self.artist.lower()
            song = genius.search_song(artist=self.artist, title=self.title)
            song_artist_lc = song.artist.lower() if song else ''
            artist_match = song_artist_lc in artist_lc or artist_lc in song_artist_lc
            if song and not artist_match:
                if not self.confirm_song_match(song.artist):
                    # rejected first choice so tray again with just the title
                    song = genius.search_song(title=self.title)
                    song_artist_lc = song.artist.lower() if song else ''
                    artist_match = song_artist_lc in artist_lc or artist_lc in song_artist_lc
                    if song and not artist_match and not self.confirm_song_match(song.artist):
                        song = None
    
            if song:
                album = song.album.get('name', '') if song.album and artist_match else ''
                logit(f"Found song {song.title} on {album}: {song.api_path}")
                lyrics = song.lyrics
                url = song.url
    
        except Exception as ex:
            logit(f"Error fetching Genius lyrics {self.title}, {ex}")
    
        return (url, lyrics, album)

    def get_lyrics(self):
        (url, lyrics, album) = self.get_lyrics_shazam()
        if not url or not lyrics:
            (url, lyrics, album) = self.get_lyrics_genius()

        return (url, lyrics, album)


    # get song info by hitting: 
    # https://www.shazam.com/services/amapi/v1/catalog/US/search?types=songs&limit=1&term=<SONG_ARTIST_TERM>
    # where <SONG_ARTIST_TERM> is a string of the artist name and song title. from the result fish out
    # the song ID and the hypenated title from the result.
    def shazam_lookup(self):
        id = title = None
        artist_lc = self.artist.lower()
        search_term=f"{self.artist} {self.title}"
        term_safe = urllib.parse.quote(search_term)
    
        url = f"https://www.shazam.com/services/amapi/v1/catalog/US/search?types=songs&limit=1&term={term_safe}"
        req = urllib.request.Request(url, method=f'GET')
        with urllib.request.urlopen(req, timeout=10, context=self.SSL_CONTEXT) as response:
            res_obj  = json.loads(response.read())
            result = res_obj['results']
            songs = result['songs']
            data = songs['data']
            song = data[0]
            id = song['id']
            attrs = song['attributes']
            song_artist = attrs['artistName'].lower()
            have_match = artist_lc in song_artist or song_artist in artist_lc
            if have_match or self.confirm_song_match(song_artist):
                album = attrs['albumName']
                previews = attrs['previews']
                url = attrs['url']
                ALBUM_KEY = '/album/'
                ALBUM_KEY_LEN = len(ALBUM_KEY)
                idx1 = url.find(ALBUM_KEY) 
                idx2 = url.find('/', idx1 + ALBUM_KEY_LEN + 1)
                title = url[idx1+ALBUM_KEY_LEN : idx2]
                album = album if have_match else ''

            return (id, title, album)
    
    # get song lyrics by fetching the shazam page and scraping the lyrics by looking for the 
    # '"text": "' anchor and pulling everything between the start & end quotes. sanity check the
    # indicies so we are insulated against returing false data in the case of a page format change.
    def get_lyrics_shazam(self):
        album = lyrics = url = ''
        try:
            (id, title, album) = self.shazam_lookup()
            if id and title:
                url = f"https://www.shazam.com/song/{id}/{title}"
                req = urllib.request.Request(url, method=f'GET')
                with urllib.request.urlopen(req, timeout=15, context=self.SSL_CONTEXT) as response:
                    page  = response.read().decode()
                    LYRICS_SECTION_KEY = '"lyrics": {'
                    lyrics_section_idx = page.find(LYRICS_SECTION_KEY)
                    LYRICS_START_KEY = '"text": "'
                    lyrics_start_idx = page.find(LYRICS_START_KEY, lyrics_section_idx) + len(LYRICS_START_KEY)
                    LYRICS_END_KEY = '},'
                    lyrics_end_idx = page.find(LYRICS_END_KEY, lyrics_start_idx)
                    lyrics_offset = lyrics_start_idx - lyrics_section_idx
                    character_cnt = lyrics_end_idx - lyrics_start_idx

                    # sanity check that the offsets are within expetect range else return NONE
                    if 0 < lyrics_offset < 100 and 10 < character_cnt < 10000:
                        lyrics = page[lyrics_start_idx : lyrics_end_idx]
                    else:
                        logit(f"lyrics not found: {lyrics_start_idx}, {lyrics_end_idx}, {lyrics_offset}, {character_cnt}")
        except Exception as ex:
            logit(f"Exectpion while fetching Shazam lyrics: {url}, {ex}")
            url = None
        
        return (url, lyrics, album)
    
    
    def explicit_check(self):
        BAD_WORDS = [ "asshole", "bullshit", "cocksucker", "cunt", "fuck", "fucker", \
                      "fuckers", "fucking", "motherfucker", "motherfuckers", "nigger", "piss", \
                      "shit", "tits" ]

        self.fcc_status = self.FCC_NOT_FOUND
        if not self.artist or self.artist == '-' or not self.title or self.title == '-':
            return

        (url, lyrics, album) = self.get_lyrics()
        self.album = album
        # strip protocol for readability
        url = url[8:] if url and url.startswith('https://') else url
        self.song_url = url
        logit(f"Lyric search for {self.title} by {self.artist} found: {url}")

        if lyrics:
            lyrics_lc = lyrics.lower()
            words = re.findall(r'\w+', lyrics_lc)
            word_counts = Counter(words)

            self.explicit_msg = ''
            seperator = ''
            for word in BAD_WORDS:
                if (count := word_counts.get(word, 0)) > 0:
                    self.explicit_msg = f'{self.explicit_msg}{seperator}{word} {count}x'
                    seperator = ', '

            if self.explicit_msg:
                self.fcc_status = self.FCC_DIRTY
            else:
               self.fcc_status = self.FCC_CLEAN


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: {} <ARTIST> <TRACK>".format(sys.argv[0]))
        sys.exit(1)
    else:
        SystemConfig.load_config('')
        artist_name = sys.argv[1]
        song_title = sys.argv[2]
        check = FCCChecker(artist_name, song_title)
        print(f'{song_title}:\nAlbum: {check.album}\nURL: {check.song_url}\nMessage: {check.explicit_msg}')


import re, urllib, ssl, json, re
from collections import Counter

from models import Track
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
# julia king - insomnia (clean, check correct author)
# Don Williams - Leaving Louisiana in Broad Daylight (clean, rodney crowell)
# Zach Bryan - Bad News (motherfucker)
# steven stills - season of the witch (clean, donovan)
# Radiohead - creep (fuckin')
# Congress of Wonders - Star Trip (clean, Genius)
# India Ramey - Scattered And Smothered (fucked)
# Bill Kirchen Honky - Tonk Hellfire (should find album even with no spaces around hyphen)
# Tom Rush - Jamaica say you will (should find Shazam lyrics. instead uses genius version)

class FCCChecker():
    SSL_CONTEXT = ssl._create_unverified_context()

    FCC_CLEAN = 'CLEAN'
    FCC_DIRTY = 'DIRTY'
    FCC_NOT_FOUND = 'NOT_FOUND'
    FCC_UNKNOWN = '-'
    FCC_STATUS_AR = [FCC_CLEAN, FCC_DIRTY, FCC_NOT_FOUND, FCC_UNKNOWN]

    def __init__(self, track):
        super().__init__()
        self.track = track
        self.label = None
        self.album = None
        self.song_url = None
        self.fcc_status = self.FCC_NOT_FOUND
        self.explicit_msg = ''
        self.explicit_count = 0

        if self.track.have_artist() and self.track.have_title():
            (url, lyrics, album) = self.get_lyrics()
            self.album = album
            # strip protocol for readability
            url = url[8:] if url and url.startswith('https://') else url
            self.song_url = url
            logit(f"Lyric search for {self.track.title} by {self.track.artist} found: {url}")
            self.explicit_check(lyrics)

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
    
        
    def confirm_song_match(self, found_artist, found_title):
        msg = f"FCC check found lyrics for {found_title} by {found_artist} instead of {self.track.title} by {self.track.artist}. Is this the same song?"
        return messagebox.askyesno("Confirm Lyrics", msg)

    def get_lyrics_genius(self):
        url = lyrics = album =None
        if not SystemConfig.genius_apikey:
            logit("Skipping genius check, api key not set")
            return (None, None, None)
    
        try:
            genius = lyricsgenius.Genius(SystemConfig.genius_apikey, skip_non_songs=True, remove_section_headers=True)
            artist_lc = self.track.artist.lower()
            # search by title only so that we get lyrics for cover versions
            song = genius.search_song(title=self.track.get_primary_title())
            song_artist_lc = song.artist.lower() if song else ''
            artist_match = song_artist_lc in artist_lc or artist_lc in song_artist_lc
            if song and not artist_match:
                if not self.confirm_song_match(song.artist, song.title):
                    # rejected first choice so tray again with just the title
                    song = genius.search_song(title=self.track.title)
                    song_artist_lc = song.artist.lower() if song else ''
                    artist_match = song_artist_lc in artist_lc or artist_lc in song_artist_lc
                    if song and not artist_match and not self.confirm_song_match(song.artist, song.title):
                        song = None
    
            if song:
                album = song.album.get('name', '') if song.album and artist_match else ''
                logit(f"Found song {song.title} on {album}: {song.api_path}")
                lyrics = song.lyrics
                url = song.url
    
        except Exception as ex:
            logit(f"Error fetching Genius lyrics {self.track.title}, {ex}")
    
        return (url, lyrics, album)

    def get_lyrics(self):
        (url, lyrics, album) = self.get_lyrics_shazam()
        if not lyrics:
            (genius_url, lyrics, genius_album) = self.get_lyrics_genius()
            if lyrics:
                url = genius_url
                album = genius_album if genius_album else album

        return (url, lyrics, album)


    # get song info by hitting: 
    # https://www.shazam.com/services/amapi/v1/catalog/US/search?types=songs&limit=1&term=<SONG_ARTIST_TERM>
    # where <SONG_ARTIST_TERM> is a string of the artist name and song title. from the result fish out
    # the song ID and the hypenated title from the result.
    def shazam_lookup(self):
        id = title = None
        search_term=f"{self.track.get_primary_artist()} {self.track.get_primary_title()}"
        term_safe = urllib.parse.quote(search_term)

        # ask for 5 items because the best match is usually but not always the 1st response
        # item so we have to search the entire result set for the best match.
        url = f"https://www.shazam.com/services/amapi/v1/catalog/US/search?types=songs&limit=5&term={term_safe}"
        req = urllib.request.Request(url, method=f'GET')
        with urllib.request.urlopen(req, timeout=10, context=self.SSL_CONTEXT) as response:
            res_obj  = json.loads(response.read())
            result = res_obj['results']
            songs = result['songs']
            data = songs['data']
            full_match_song = None
            title_match_songs = []
            album_name = None
            for song in enumerate(data):
                song = song[1]
                attrs = song['attributes']
                song_artist = attrs['artistName']
                artist_match = self.track.have_artist_match(song_artist)
                song_title = attrs['name'].strip()
                title_match =  self.track.have_title_match(song_title)
                if artist_match and title_match:
                    full_match_song = song
                    album_name = attrs['albumName']
                    if not album_name.endswith(' - Single'):
                        break
                elif title_match:
                    title_match_songs.append(song)

            target_song = full_match_song
            if not target_song:
                for candidate in title_match_songs:
                    attrs = song['attributes']
                    if self.confirm_song_match(attrs['artistName'], attrs['name']):
                        target_song = candidate
                        break

            if target_song:
                attrs = target_song['attributes']
                url = attrs['url']
                ALBUM_KEY = '/album/'
                idx1 = url.find(ALBUM_KEY)
                ALBUM_KEY_LEN = len(ALBUM_KEY)
                idx2 = url.find('/', idx1 + ALBUM_KEY_LEN + 1)
                title = url[idx1+ALBUM_KEY_LEN : idx2]
                return (target_song['id'], title, album_name, attrs['hasLyrics'])

        return(None, None, None, None)
    
    # get song lyrics by fetching the shazam page and scraping the lyrics by looking for the 
    # '"text": "' anchor and pulling everything between the start & end quotes. sanity check the
    # indices so we are insulated against returning false data in the case of a page format change.
    def get_lyrics_shazam(self):
        album = lyrics = url = ''
        try:
            (id, title, album, has_lyrics) = self.shazam_lookup()
            if id and title and has_lyrics:
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
            logit(f"Exception while fetching Shazam lyrics: {url}, {ex}")
            url = None
        
        return (url, lyrics, album)
    
    
    def explicit_check(self, lyrics):
        BAD_WORD_PATTERNS = [r"\basshole\b", r"\b[a-z]*shit[a-z]*\b", r"\b[a-z]*fuck[a-z]*\b", \
                             r"\bcocksucker\b", r"\bcunt\b", r"\bnigger\b", r"\bpiss\b", \
                             r"\btits\b"]

        if not lyrics:
            return

        lyrics_lc = lyrics.lower()
        self.explicit_msg = ''
        seperator = ''

        for pattern in BAD_WORD_PATTERNS:
            matches = re.findall(pattern, lyrics_lc)
            match_count = len(matches)
            self.explicit_count += match_count
            if match_count > 0:
                self.explicit_msg = f'{self.explicit_msg}{seperator}{matches[0]} {match_count}x'
                seperator = ', '

        if self.explicit_msg:
            self.fcc_status = self.FCC_DIRTY
        else:
            self.fcc_status = self.FCC_CLEAN


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: {} <ARTIST> <TRACK>".format(sys.argv[0]))
        sys.exit(1)
    else:
        SystemConfig.load_config('')
        artist_name = sys.argv[1]
        song_title = sys.argv[2]
        if artist_name == "explicit_check":
            TEST_COUNT = 11
            TEST_STRING = '''ass Asshole\n Cock, cockSucker, fuck; fuckin' motherfucker, fucked shit shithead bullshit - nigger'''
            track = Track()
            track.title = track.artist = '-'
            checker = FCCChecker(track)
            checker.explicit_check(TEST_STRING)
            status = "pass" if checker.explicit_count == TEST_COUNT else "fail"
            print(f"Test check status: {status}, found: {checker.explicit_count}, expected: {TEST_COUNT}\nMessage: {checker.explicit_msg}")
        else:
            track = Track()
            track.title = song_title
            track.artist = artist_name
            check = FCCChecker(track)
            print(f'{song_title}:\nAlbum: {check.album}\nURL: {check.song_url}\nMessage: {check.explicit_msg}')


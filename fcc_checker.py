import re
from collections import Counter
from system_config import SystemConfig
import sys
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import lyricsgenius
from djutils import logit
from tkinter import messagebox

# test cases:
# dylan ; hurricane
# pink floyd ; money
# james mcmurtry ; can't make it here
# Orville Peck & Margo Price - You're an Asshole
# julia king - insomnia
# Don Williams - Leaving Louisiana in Broad Daylight

class FCCChecker():
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
        self.fcc_status = self.FCC_NOT_FOUND
        self.explicit_msg = ''
        self.explict_check()

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
    
    def get_lyrics_genius(self):
        retval = None
        if not SystemConfig.genius_apikey:
            return None
    
        try:
            genius = lyricsgenius.Genius(SystemConfig.genius_apikey, skip_non_songs=True, remove_section_headers=True)
            song = genius.search_song(title=self.title, artist=self.artist)
            have_artist = True
            if  not song and (song := genius.search_song(title=self.title)):
                have_artist = False
                msg = f"FCC check found lyrics for {self.title} by {song.artist} instead of {self.artist}. Is this the same song?"
                if not messagebox.askyesno("Confirm Lyrics", msg):
                    song = None
    
            # TODO check for artist match, e.g. steven stills season of the witch
            if song:
                logit(f"Found song {song.title}: {song.api_path}, {have_artist}")
                self.album = song.album.get('name', '') if have_artist else ''
                retval = song.lyrics
    
        except Exception as ex:
            logit(f"Error fetching Genius lyrics {self.title}, {ex}")
    
        return retval
    
    
    def explict_check(self):
        BAD_WORDS = ["shit", "fuck", "asshole", 'nigger', "bullshit"]

        self.fcc_status = self.FCC_NOT_FOUND
        if not self.artist or self.artist == '-' or not self.title or self.title == '-':
            return

        lyrics = self.get_lyrics_genius()
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
        artist_name = sys.argv[1]
        song_title = sys.argv[2]
        status = FCCChecker(artist_name, song_title)
        print(f'{song_title}: {status}')


import json
import ssl
import tkinter.messagebox
import urllib
from  tkinter import messagebox

import yaml

from djutils import logit

class SystemConfig():
    spotify_id = ''
    spotify_secret = ''
    genius_apikey = ''
    playlist_host = ''
    zookeeper_host = ''
    zookeeper_apikey = ''
    output_device = ''
    user_apikey = ''
    use_proxy = False

    @staticmethod
    def load_config(user_apikey_arg):
        config_dict = {} 
        try:
            with open('system_config.yaml', 'r') as file:
                config_dict = yaml.safe_load(file)
        except Exception as ex:
            logit(f'Error reading system_config.yaml configuration file: {ex}')

        config_dict = config_dict if config_dict else {} 
        SystemConfig.playlist_host = config_dict.get('PLAYLIST_HOST', 'https://kzsu.stanford.edu')
        SystemConfig.zookeeper_host = config_dict.get('ZOOKEEPER_HOST', 'https://zookeeper.stanford.edu')
        SystemConfig.zookeeper_apikey = config_dict.get('ZOOKEEPER_APIKEY', '')
        SystemConfig.spotify_id = config_dict.get('SPOTIFY_ID', '')
        SystemConfig.spotify_secret = config_dict.get('SPOTIFY_SECRET', '')
        SystemConfig.genius_apikey = config_dict.get('GENIUS_APIKEY', '')
        SystemConfig.output_device = config_dict.get('OUTPUT_DEVICE', '')
        SystemConfig.user_apikey = config_dict.get('USER_APIKEY', '')
        SystemConfig.use_proxy = config_dict.get('USE_PROXY', False)

        if user_apikey_arg:
            SystemConfig.user_apikey = user_apikey_arg

        if SystemConfig.user_apikey and (not SystemConfig.spotify_id or not SystemConfig.spotify_secret or not SystemConfig.genius_apikey):
            try:
                ssl_context = ssl._create_unverified_context()
                req = urllib.request.Request(SystemConfig.playlist_host + '/djtool/helpertokens/')
                req.add_header("Content-type", "application/vnd.api+json")
                req.add_header("Accept", "text/plain")
                req.add_header("X-APIKEY", SystemConfig.user_apikey)
                with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                    resp_obj = json.loads(response.read())
                    if not SystemConfig.spotify_id:
                        SystemConfig.spotify_id = resp_obj.get('spotify_id', None)

                    if not SystemConfig.spotify_secret:
                        SystemConfig.spotify_secret = resp_obj.get('spotify_secret', None)

                    if not SystemConfig.genius_apikey:
                        SystemConfig.genius_apikey = resp_obj.get('genius_apikey', None)
            except Exception as e:
                logit(f"Exception geting apikeys, {e}, {SystemConfig.user_apikey}")

    @staticmethod
    def check_have_user_key():
        msg = None
        if not SystemConfig.user_apikey:
            msg = '''This feature is not be available because your user apikey has not been set. Set it by visiting https://kzsu.stanford.edu/internal/profile and clicking the Add Key button. Then copy the generated key and paste it into the User API Key field in the user configuration dialog which is accessed by clicking File->Configure...'''

            tkinter.messagebox.showwarning("Configuration Error", msg)

        return not msg

    @staticmethod
    def check_have_spotify_key():
        msg = None
        if not SystemConfig.spotify_id or not SystemConfig.spotify_secret:
            msg = '''This feature is not available because the Spotify apikeys have not been set. Check that your user key in the File->Configuration dialog matches the api key at https://kzsu.stanford.edu/internal/profile'''

            tkinter.messagebox.showwarning("Configuration Error", msg)

        return not msg

    @staticmethod
    def check_have_genius_key():
        msg = None
        if not SystemConfig.genius_apikey:
            msg = '''This feature is not available because the Genius apikey has not been set. Check that your user key in the File->Configuration dialog matches the api key at https://kzsu.stanford.edu/internal/profile'''

            tkinter.messagebox.showwarning("Configuration Error", msg)

        return not msg

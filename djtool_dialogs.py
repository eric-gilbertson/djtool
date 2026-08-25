import webbrowser
from tkinter import ttk, simpledialog
import tkinter as tk
from fcc_checker import FCCChecker
from models import UserConfiguration, Track
from commondefs import API_KEY_LEN
from system_config import SystemConfig
import fcc_checker


class SelectAlbumDialog(simpledialog.Dialog):
    def __init__(self, parent, artist, track, album_choices):
        self.artist = artist
        self.track = track
        self.album_choices = album_choices
        self.album = ''
        self.ok_clicked = False
        super().__init__(parent, f'Select Album')

    def body(self, master):
        self.choices_entry = tk.Text(master, borderwidth=1, relief="solid", width=80)
        self.choices_entry.bind("<Double-1>", lambda e: self._select_row(e))
        self.choices_entry.config(cursor="arrow")

        self.choice_entry = tk.Entry(master, width=60)
        self.track_info = tk.Entry(master, width=60)

        idx = 0
        albums = ''
        for title in self.album_choices:
            albums = albums + f"{idx}: {title}\n"
            idx = idx + 1

        self.choices_entry.insert("1.0", albums)
        self.track_info.insert(0, f'{self.artist} - {self.track}')

        if idx > 0:
            self.choice_entry.insert(0, '0')

        self.choice_entry.focus_set()
 
        # Place widgets
        self.track_info.grid(row=1, column=0, padx=0, pady=5)
        self.choices_entry.grid(row=2, column=0, padx=0, pady=5)
        self.choice_entry.grid(row=3, column=0, padx=5, pady=5)

    def apply(self):
        # When Save is clicked
        self.ok_clicked = True

        choice = self.choice_entry.get()
        choice_int = -1
        try:
            if 0 < len(choice) <= 2:
                choice_int = int(choice)
        except ValueError as e:
            pass

        if len(choice) == 0:
            self.ok_clicked = False
            self.album = ''
        elif 0 <= choice_int < len(self.album_choices):
            self.album = self.album_choices[choice_int]
        else:
            self.album = choice # assume user entered track

        self.destroy_dialog()

    def _select_row(self, event):
        index = self.choices_entry.index(f"@{event.x},{event.y}")
        line_number = int(index.split('.')[0]) - 1
        if line_number >= len(self.album_choices):
            return

        self.ok_clicked = True
        self.album = self.album_choices[line_number]
        self.destroy_dialog()
    
    def destroy_dialog(self):
        self.grab_release() # Release grab before destroying
        self.destroy()
        

#def custom_dialog():
#    # Create a Toplevel window (acts as the dialog)
#    win = tk.Toplevel(root)
#    win.title("Custom Dialog")
#
#    # Add a message label
#    message = "Do you want to proceed or stop?"
#    tk.Label(win, text=message).pack(pady=20)
#
#    # Add custom buttons
#    # The 'command' ties the button action to a function
#    tk.Button(win, text='Proceed', command=lambda: handle_choice(win, "proceed")).pack(side=tk.LEFT, padx=10, pady=10)
#    tk.Button(win, text='Stop', command=lambda: handle_choice(win, "stop")).pack(side=tk.RIGHT, padx=10, pady=10)
#
#def handle_choice(window, choice):
#    print(f"User chose: {choice}")
#    window.destroy() # Close the custom dialog after the choice is made

class LiveShowDialog(simpledialog.Dialog):
    def __init__(self, parent, show_title, show_start, apikey):
        self.parent = parent
        self.show_title = show_title
        self.show_start = show_start
        self.show_title_entry = None
        self.apikey = apikey
        self.ok_clicked = False
        self.error_label = None
        super().__init__(parent, "Live Show Info")

    def body(self, master):
        info_msg = "Enter the name of your Zookeeper playlist. Note that playlist must be created in Zookeeper before performing this operation."

        row = 0
        tk.Label(master, text=info_msg, wraplength=450, justify=tk.LEFT).grid(row=row, column=0, columnspan=2, sticky="ew", padx=0, pady=0)

        row += 1
        tk.Label(master, text="Show Title:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.show_title_entry = tk.Entry(master, width=40)
        self.show_title_entry.insert(0, self.show_title)
        self.show_title_entry.bind('<Return>', self.ok)
        self.show_title_entry.grid(row=row, column=1, padx=5, pady=5)

        row += 1
        tk.Label(master, text="API Key:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        self.apikey_entry = tk.Entry(master, width=40)
        self.apikey_entry.insert(0, self.apikey)
        self.apikey_entry.bind('<Return>', self.ok)
        self.apikey_entry.grid(row=row, column=1, padx=5, pady=5)

        row += row
        self.error_label = tk.Label(master, fg='red', wraplength=450, justify=tk.LEFT)
        self.error_label.grid(row=row, column=0, columnspan=2, sticky="ew", padx=0, pady=0)

        return self.show_title_entry  # focus on artist field by default

    def buttonbox(self):
        box = tk.Frame(self)
        self.ok_button = tk.Button(box, text="OK", width=10, command=self.ok)
        self.ok_button.pack(side=tk.LEFT, padx=5, pady=5)
        cancel_button = tk.Button(box, text="Cancel", width=10, command=self.cancel)
        cancel_button.pack(side=tk.LEFT, padx=5, pady=5)
        box.pack()

    def validate(self):
        msg = None
        if len(self.show_title_entry.get()) == 0:
            msg = 'Show title is required'
        elif len(self.apikey_entry.get()) != API_KEY_LEN:
            msg = f'Invalid API KEY. The key must be {API_KEY_LEN} characters long'

        if msg:
            self.error_label.config(text=msg)

        return not msg


    def apply(self):
        title = self.show_title_entry.get()
        apikey = self.apikey_entry.get()
        self.parent.check_show_playlist(title, apikey, '')

    def cancel(self, event=None):
        # This is called when 'Cancel' is pressed or window is closed
        super().cancel(event)
        self.parent.clear_live_show()

class UserConfigurationDialog(simpledialog.Dialog):
    def __init__(self, parent):
        self.ok_clicked = False
        super().__init__(parent, "Configuration")

    def body(self, master):
        row_num = 0
        tk.Label(master, text="Show Title:").grid(row=row_num, column=0, sticky="e", padx=5, pady=5)
        self.show_title_entry = tk.Entry(master, width=40)
        self.show_title_entry.insert(0, UserConfiguration.show_title)
        self.show_title_entry.grid(row=row_num, column=1, padx=5, pady=5)

        row_num = row_num + 1
        tk.Label(master, text="Show Start:").grid(row=row_num, column=0, sticky="e", padx=5, pady=5)
        self.show_start_combo = ttk.Combobox(master, state="readonly", width=15)
        self.show_start_combo.grid(row=row_num, column=1, sticky='w', padx=5, pady=5)
        time_values = [
            'None', '12 am', '1 am', '2 am', '3 am', '4 am', '5 am', '6 am', '7 am', '8 am', '9 am', '10 am', '11 am',
            '12 pm', '1 pm', '2 pm', '3 pm', '4 pm', '5 pm', '6 pm', '7 pm', '8 pm', '9 pm', '10 pm', '11 pm', 'None'
        ]

        self.show_start_combo['values'] = time_values
        print(f"time {UserConfiguration.show_start_time}")
        if UserConfiguration.show_start_time and UserConfiguration.show_start_time != 'None':
            time_ar = UserConfiguration.show_start_time.split(' ')
            hour = int(time_ar[0])
            hour = 0 if hour == 12 and time_ar[1] == 'am' else hour
            hour = hour + 12 if time_ar[1] == 'pm' and hour != 12 else hour
            self.show_start_combo.set(time_values[hour + 1])
        else:
            self.show_start_combo.set('None')

        row_num = row_num + 1
        tk.Label(master, text="User API Key:").grid(row=row_num, column=0, sticky="e", padx=5, pady=5)
        self.user_apikey_entry = tk.Entry(master, width=40)
        self.user_apikey_entry.insert(0, UserConfiguration.user_apikey)
        self.user_apikey_entry.grid(row=row_num, column=1, padx=5, pady=5)

        row_num = row_num + 1
        tk.Label(master, text="Zookeeper API Key:").grid(row=row_num, column=0, sticky="e", padx=5, pady=5)
        self.playlist_apikey_entry = tk.Entry(master, width=40)
        self.playlist_apikey_entry.insert(0, UserConfiguration.playlist_apikey)
        self.playlist_apikey_entry.grid(row=row_num, column=1, padx=5, pady=5)

        return self.show_title_entry  # focus on artist field by default

    def validate(self):

        keylen1 = len(self.user_apikey_entry.get())
        is_okay1 = keylen1 == 0 or keylen1 == API_KEY_LEN
        if not is_okay1:
            tk.messagebox.showwarning(title="Error", message=f'The length of the User API Key entry is incorrect. This value should be {API_KEY_LEN} characters long.', parent=self)

        keylen2 = len(self.playlist_apikey_entry.get())
        is_okay2 = keylen2 == 0 or keylen2 == API_KEY_LEN
        if not is_okay2:
            tk.messagebox.showwarning(title="Error", message=f'The length of the Playlist API Key entry is incorrect. This value should be {API_KEY_LEN}  characters long.', parent=self)

        return is_okay1 and is_okay2


    def apply(self):
        self.ok_clicked = True
        update_system_apikey = SystemConfig.user_apikey == UserConfiguration.user_apikey

        UserConfiguration.show_title = self.show_title_entry.get()
        UserConfiguration.user_apikey = self.user_apikey_entry.get()
        UserConfiguration.playlist_apikey = self.playlist_apikey_entry.get()
        UserConfiguration.show_start_time = self.show_start_combo.get()

        # update iff using the user key as the system key.
        if update_system_apikey:
            SystemConfig.user_apikey = UserConfiguration.user_apikey
            SystemConfig.load_config(UserConfiguration.user_apikey)

        UserConfiguration.save_config()

class TrackEditDialog(simpledialog.Dialog):
    def __init__(self, parent, track):
        self.fcc_comment_lbl = None
        self.parent = parent
        self.ok_clicked = False
        self.track_artist = track.artist if track.artist else ''
        self.track_title  = track.title if track.title else ''
        self.track_album = track.album if track.album else ''
        self.track_label = track.label if track.label else ''
        self.track_fcc_status = track.fcc_status
        self.track_fcc_comment = track.fcc_comment if track.fcc_comment else ''
        self.track_song_url = track.song_url

        # manuaul lyrics check
        self.lyrics = None
        self.lyrics_check_but = None

        super().__init__(parent, "Edit Track")


    def body(self, master):
        #self.grab_set()
        #self.transient(self.parent)  # Set as child of parent

        # Create labels
        tk.Label(master, text="Artist:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text="Title:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text="Album:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text="Label:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        tk.Label(master, text="FCC:").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        link = tk.Label(master, text=self.track_song_url, fg='green', cursor="hand2")
        link.grid(row=5, column=1, sticky="w", padx=0, pady=0)
        song_url = self.track_song_url if self.track_song_url else ''
        if song_url:
            have_prefix = self.track_song_url.startswith("http")
            song_url = ("" if have_prefix else "https://") + self.track_song_url
 
        link.bind("<Button-1>", lambda e : webbrowser.open_new(song_url))
        self.fcc_comment_lbl = tk.Label(master, text=self.track_fcc_comment)
        self.fcc_comment_lbl.grid(row=6, column=1, sticky="w", padx=0, pady=0)

        self.lyrics = tk.Text(master, width=50, height=15)
        lyric_search_key = f"{self.track_artist} - {self.track_title}\n"
        self.lyrics.insert("1.0", lyric_search_key)
        self.lyrics.grid(row=7, column=1, sticky="w", padx=0, pady=0)
        self.lyrics_check_but = tk.Button(master, text="Check Lyrics", width=10, command=self.check_lyrics)
        self.lyrics_check_but.grid(row=8, column=1, sticky="w", padx=0, pady=0)



        # Create entry fields with initial values
        self.artist_entry = tk.Entry(master, width=40)
        self.artist_entry.insert(0, self.track_artist)

        self.title_entry = tk.Entry(master, width=40)
        self.title_entry.insert(0, self.track_title)

        self.album_entry = tk.Entry(master, width=40)
        self.album_entry.insert(0, self.track_album)

        self.label_entry = tk.Entry(master, width=40)
        self.label_entry.insert(0, self.track_label)

        self.fcc_status_combo = ttk.Combobox(master, state="readonly", width=20)
        self.fcc_status_combo.insert(0, self.track_fcc_status)
        self.fcc_status_combo['values'] = FCCChecker.FCC_STATUS_AR
        self.fcc_status_combo.set(self.track_fcc_status)

        # Place widgets
        self.artist_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.title_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.album_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        self.label_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        self.fcc_status_combo.grid(row=4, column=1, sticky='w', padx=5, pady=5)

        return self.artist_entry  # focus on artist field by default

    def apply(self):
        # When Save is clicked
        self.ok_clicked = True
        self.track_artist = self.artist_entry.get()
        self.track_title = self.title_entry.get()
        self.track_album = self.album_entry.get()
        self.track_label = self.label_entry.get()
        self.track_fcc_status = self.fcc_status_combo.get()
        if self.track_fcc_status == FCCChecker.FCC_UNKNOWN:
            self.track_fcc_comment = ''
            self.track_song_url = ''


    def check_lyrics(self):
        lyrics = self.lyrics.get("1.0", "end-1c")
        if len(lyrics) < 200:
            tk.messagebox.showwarning(title="Error", message=f'The lyrics appear to be too short.', parent=self)
        else:
            fcc_check = FCCChecker(Track())
            fcc_check.explicit_check(lyrics)
            self.track_fcc_status = fcc_check.fcc_status
            self.fcc_status_combo.set(self.track_fcc_status)
            self.track_fcc_comment = fcc_check.explicit_msg
            self.fcc_comment_lbl.config(text=fcc_check.explicit_msg)






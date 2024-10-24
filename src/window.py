import time, re, sys
import gi, os, subprocess
import pickle
from .avatar import AvatarHandler

from .presentation import PresentationWindow
from .gtkobj import File, CopyBox, BarChartBox, MultilineEntry
from .constants import AVAILABLE_LLMS, AVAILABLE_SMART_PROMPTS, AVAILABLE_TRANSLATORS, EXTRA_PROMPTS, PROMPTS, AVAILABLE_TTS, AVAILABLE_STT, AVAILABLE_AVATARS, AVAILABLE_PROMPTS
from gi.repository import Gtk, Adw, Pango, Gio, Gdk, GObject, GLib
from .stt import AudioRecorder
from .extra import ReplaceHelper, markwon_to_pango, override_prompts, replace_variables
import threading
import posixpath
import shlex,json
import random
from pydub import AudioSegment

from .extensions import ExtensionLoader

class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        self.first_load = True
        super().__init__(*args, **kwargs)
        self.set_default_size(1400, 800) #(1500, 800) to show everything
        self.main_program_block = Adw.Flap(flap_position=Gtk.PackType.END,modal=False,swipe_to_close=False,swipe_to_open=False)
        self.main_program_block.set_name("hide")
        self.check_streams={"folder":False,"chat":False}


        self.path = GLib.get_user_data_dir()
        self.directory = GLib.get_user_config_dir()
        # Pip directory for optional modules
        self.pip_directory = os.path.join(self.directory, "pip")
        self.extension_path = os.path.join(self.directory, "extensions")
        self.extensions_cache = os.path.join(self.directory, "extensions_cache")
        if not os.path.exists(self.extension_path):
            os.makedirs(self.extension_path)
        sys.path.append(self.pip_directory)

        if not os.path.exists(self.path):
            os.makedirs(self.path)
        self.filename = "chats.pkl"
        if os.path.exists(self.path + self.filename):
            with open(self.path + self.filename, 'rb') as f:
                self.chats = pickle.load(f)
        else:
            self.chats = [{"name": _("Chat ")+"1", "chat": []}]

        # Init Settings
        self.avatar_enabled = None
        settings = Gio.Settings.new('moe.nyarchlinux.assistant')
        self.settings = settings
        self.update_settings()

        # Build Window
        self.set_titlebar(Gtk.Box())
        self.chat_panel = Gtk.Box(hexpand_set=True, hexpand=True)
        self.chat_panel.set_size_request(450, -1)
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu = Gio.Menu()
        menu.append(_("Thread editing"), "app.thread_editing")
        menu.append(_("Extensions"), "app.extension")
        menu.append(_("Settings"), "app.settings")
        menu.append(_("Keyboard shorcuts"), "app.shortcuts")
        menu.append(_("About"), "app.about")
        menu_button.set_menu_model(menu)
        self.chat_block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, css_classes=["view"])
        self.chat_header = Adw.HeaderBar(css_classes=["flat","view"])
        self.chat_header.set_title_widget(Gtk.Label(label=_("Chat"), css_classes=["title"]))
        
        # Header box - Contains the buttons that must go in the left side of the header
        self.headerbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True) 
        # Mute TTS Button 
        self.mute_tts_button = Gtk.Button(css_classes=["flat"], icon_name="audio-volume-muted-symbolic", visible=False)
        self.mute_tts_button.connect("clicked", self.mute_tts)
        self.headerbox.append(self.mute_tts_button)
        # Flap button 
        self.flap_button_left = Gtk.ToggleButton.new()
        self.flap_button_left.set_icon_name(icon_name='sidebar-show-right-symbolic')
        self.flap_button_left.connect('clicked', self.on_flap_button_toggled)
        self.headerbox.append(child=self.flap_button_left)
        # Add headerbox to default parent
        self.chat_header.pack_end(self.headerbox)

        self.left_panel_back_button = Gtk.Button(css_classes=["flat"], visible=False)
        icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="go-previous-symbolic"))
        icon.set_icon_size(Gtk.IconSize.INHERIT)
        box = Gtk.Box(halign=Gtk.Align.CENTER)
        box.append(icon)
        self.left_panel_back_button.set_child(box)
        self.left_panel_back_button.connect("clicked", self.go_back_to_chats_panel)
        self.chat_header.pack_start(self.left_panel_back_button)
        self.chat_block.append(self.chat_header)
        self.chat_block.append(Gtk.Separator())
        self.chat_panel.append(self.chat_block)
        self.chat_panel.append(Gtk.Separator())

        self.main = Adw.Leaflet(fold_threshold_policy=True, can_navigate_back=True, can_navigate_forward=True)
        self.streams=[]
        self.chats_main_box = Gtk.Box(hexpand_set=True)
        self.chats_main_box.set_size_request(300, -1)
        self.chats_secondary_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        self.chat_panel_header = Adw.HeaderBar(css_classes=["flat"],  show_end_title_buttons = False)
        self.chat_panel_header.set_title_widget(Gtk.Label(label=_("History"), css_classes=["title"]))
        self.chats_secondary_box.append(self.chat_panel_header)
        self.chats_secondary_box.append(Gtk.Separator())
        self.chat_panel_header.pack_end(menu_button)
        self.chats_buttons_block = Gtk.ListBox(css_classes=["separators","background"])
        self.chats_buttons_block.set_selection_mode(Gtk.SelectionMode.NONE)
        self.chats_buttons_scroll_block = Gtk.ScrolledWindow(vexpand=True)
        self.chats_buttons_scroll_block.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.chats_buttons_scroll_block.set_child(self.chats_buttons_block)
        self.chats_secondary_box.append(self.chats_buttons_scroll_block)
        button = Gtk.Button(valign=Gtk.Align.END,css_classes=["suggested-action"], margin_start=7, margin_end=7,  margin_top=7, margin_bottom=7)
        button.set_child(Gtk.Label(label=_("Create a chat")))
        button.connect("clicked", self.new_chat)
        self.chats_secondary_box.append(button)
        self.chats_main_box.append(self.chats_secondary_box)
        self.chats_main_box.append(Gtk.Separator())
        self.main.append(self.chats_main_box)
        self.main.append(self.chat_panel)
        self.main.set_visible_child(self.chat_panel)
        self.explorer_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["background","view"])
        self.explorer_panel.set_size_request(420, -1)
        self.explorer_panel_header = Adw.HeaderBar(css_classes=["flat"])
        self.explorer_panel.append(self.explorer_panel_header)
        self.folder_blocks_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.explorer_panel.append(self.folder_blocks_panel)
        #self.set_child(self.main_program_block)
        self.main_program_block.set_content(self.main)
        self.main_program_block.set_flap(self.explorer_panel)
        self.secondary_message_chat_block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        self.chat_block.append(self.secondary_message_chat_block)
        self.chat_list_block = Gtk.ListBox(css_classes=["separators","background","view"])
        self.chat_list_block.set_selection_mode(Gtk.SelectionMode.NONE)
        self.chat_scroll = Gtk.ScrolledWindow(vexpand=True)
        self.chat_scroll_window = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,css_classes=["background","view"])
        self.chat_scroll.set_child(self.chat_scroll_window)
        drop_target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.COPY)
        drop_target.connect('drop', self.handle_file_drag)
        self.chat_scroll.add_controller(drop_target)
        self.chat_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.chat_scroll_window.append(self.chat_list_block)
        self.notification_block = Adw.ToastOverlay()
        self.notification_block.set_child(self.chat_scroll)

        self.secondary_message_chat_block.append(self.notification_block)

        self.offers_entry_block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                        spacing=6,valign=Gtk.Align.END,halign=Gtk.Align.FILL, margin_bottom=6)
        self.chat_scroll_window.append(self.offers_entry_block)
        self.chat_controls_entry_block = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                        spacing=6,vexpand=True,valign=Gtk.Align.END,halign=Gtk.Align.CENTER, margin_top=6, margin_bottom=6)
        self.chat_scroll_window.append(self.chat_controls_entry_block)

        self.message_suggestion_buttons_array = []

        self.chat_stop_button = Gtk.Button(css_classes=["flat"])
        icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="media-playback-stop"))
        icon.set_icon_size(Gtk.IconSize.INHERIT)
        box = Gtk.Box(halign=Gtk.Align.CENTER)
        box.append(icon)
        label = Gtk.Label(label=_(" Stop"))
        box.append(label)
        self.chat_stop_button.set_child(box)
        self.chat_stop_button.connect("clicked", self.stop_chat)
        self.chat_stop_button.set_visible(False)

        button_folder_back = Gtk.Button(css_classes=["flat"])
        icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="go-previous-symbolic"))
        icon.set_icon_size(Gtk.IconSize.INHERIT)
        box = Gtk.Box(halign=Gtk.Align.CENTER)
        box.append(icon)
        button_folder_back.set_child(box)
        button_folder_back.connect("clicked", self.go_back_in_explorer_panel)

        button_folder_forward = Gtk.Button(css_classes=["flat"])
        icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="go-next-symbolic"))
        icon.set_icon_size(Gtk.IconSize.INHERIT)
        box = Gtk.Box(halign=Gtk.Align.CENTER)
        box.append(icon)
        button_folder_forward.set_child(box)
        button_folder_forward.connect("clicked", self.go_forward_in_explorer_panel)

        button_home = Gtk.Button(css_classes=["flat"])
        icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="go-home-symbolic"))
        icon.set_icon_size(Gtk.IconSize.INHERIT)
        box = Gtk.Box(halign=Gtk.Align.CENTER)
        box.append(icon)
        button_home.set_child(box)
        button_home.connect("clicked", self.go_home_in_explorer_panel)

        button_reload = Gtk.Button(css_classes=["flat"])
        icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="view-refresh-symbolic"))
        icon.set_icon_size(Gtk.IconSize.INHERIT)
        box = Gtk.Box(halign=Gtk.Align.CENTER)
        box.append(icon)
        button_reload.set_child(box)
        button_reload.connect("clicked", self.update_folder)

        box = Gtk.Box(spacing=6)
        box.append(button_folder_back)
        box.append(button_folder_forward)
        box.append(button_home)
        self.explorer_panel_header.pack_start(box)
        box = Gtk.Box(spacing=6)
        box.append(button_reload)
        # Box containing explorer panel specific buttons
        self.explorer_panel_headerbox = box
        self.main_program_block.set_reveal_flap(False)
        self.explorer_panel_header.pack_end(box)

        # Avatar
        self.avatar_handler = None
        self.avatar_widget = None
        self.avatar_flap = Adw.Flap(flap_position=Gtk.PackType.END, modal=False, swipe_to_close=False, swipe_to_open=False)
        self.avatar_flap.set_name("hide")

        self.boxw = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["background"])
        self.web_panel_header = Adw.HeaderBar(css_classes=["flat", "view"])
        self.web_panel_header.set_title_widget(Gtk.Box())
        self.boxw.append(self.web_panel_header)
        self.boxw.set_size_request(400, 0)
        self.boxw.set_hexpand(False)
        self.avatar_flap.set_flap(self.boxw)

        self.avatar_flap.set_content(self.main_program_block)
        self.flap_button_avatar = Gtk.ToggleButton.new()
        self.flap_button_avatar.set_icon_name(icon_name='avatar-symbolic')
        self.flap_button_avatar.connect('clicked', self.on_avatar_button_toggled)
        self.avatar_flap.connect("notify::reveal-flap", self.handle_second_block_change)
        self.headerbox.append(self.flap_button_avatar)
        self.set_child(self.avatar_flap)
        self.avatar_flap.set_reveal_flap(False)
        # End Live2d
        self.status = True
        self.chat_controls_entry_block.append(self.chat_stop_button)
        for text in range(self.offers):
            button = Gtk.Button(css_classes=["flat"], margin_start=6, margin_end=6)
            label = Gtk.Label(label=text, wrap=True, wrap_mode=Pango.WrapMode.CHAR)
            button.set_child(label)
            button.connect("clicked", self.send_bot_response)
            button.set_visible(False)
            self.offers_entry_block.append(button)
            self.message_suggestion_buttons_array.append(button)

        self.button_clear = Gtk.Button(css_classes=["flat"])
        icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="edit-clear-all-symbolic"))
        icon.set_icon_size(Gtk.IconSize.INHERIT)
        box = Gtk.Box(halign=Gtk.Align.CENTER)
        box.append(icon)
        label = Gtk.Label(label=_(" Clear"))
        box.append(label)
        self.button_clear.set_child(box)
        self.button_clear.connect("clicked", self.clear_chat)
        self.button_clear.set_visible(False)
        self.chat_controls_entry_block.append(self.button_clear)

        self.button_continue = Gtk.Button(css_classes=["flat"])
        icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="media-seek-forward-symbolic"))
        icon.set_icon_size(Gtk.IconSize.INHERIT)
        box = Gtk.Box(halign=Gtk.Align.CENTER)
        box.append(icon)
        label = Gtk.Label(label=_(" Continue"))
        box.append(label)
        self.button_continue.set_child(box)
        self.button_continue.connect("clicked", self.continue_message)
        self.button_continue.set_visible(False)
        self.chat_controls_entry_block.append(self.button_continue)

        self.regenerate_message_button = Gtk.Button(css_classes=["flat"])
        icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="view-refresh-symbolic"))
        icon.set_icon_size(Gtk.IconSize.INHERIT)
        box = Gtk.Box(halign=Gtk.Align.CENTER)
        box.append(icon)
        label = Gtk.Label(label=_(" Regenerate"))
        box.append(label)
        self.regenerate_message_button.set_child(box)
        self.regenerate_message_button.connect("clicked", self.regenerate_message)
        self.regenerate_message_button.set_visible(False)
        self.chat_controls_entry_block.append(self.regenerate_message_button)

        # Input message box
        input_box=Gtk.Box(halign=Gtk.Align.FILL, margin_start=6, margin_end=6,  margin_top=6, margin_bottom=6, spacing=6)
        input_box.set_valign(Gtk.Align.CENTER)
        # Text Entry
        self.input_panel = MultilineEntry()
        input_box.append(self.input_panel)
        self.input_panel.set_placeholder(_("Send a message..."))

        # Buttons on the right
        self.secondary_message_chat_block.append(Gtk.Separator())
        self.secondary_message_chat_block.append(input_box)
        # Mic button
        self.mic_button = Gtk.Button(css_classes=["suggested-action"], icon_name="audio-input-microphone-symbolic", width_request=36, height_request=36)
        self.mic_button.set_vexpand(False)
        self.mic_button.set_valign(Gtk.Align.CENTER)
        self.mic_button.connect("clicked", self.start_recording)
        input_box.append(self.mic_button)
        # Send button
        box = Gtk.Box()
        box.set_vexpand(False)
        self.send_button = Gtk.Button(css_classes=["suggested-action"], icon_name="go-next-symbolic", width_request=36, height_request=36)
        self.send_button.set_vexpand(False)
        self.send_button.set_valign(Gtk.Align.CENTER)
        box.append(self.send_button)
        input_box.append(box)
        self.input_panel.set_on_enter(self.on_entry_activate)
        self.send_button.connect('clicked', self.on_entry_button_clicked)
        self.main.connect("notify::folded", self.handle_main_block_change)
        self.main_program_block.connect("notify::reveal-flap", self.handle_second_block_change)

        self.stream_number_variable = 0
        GLib.idle_add(self.update_folder)
        GLib.idle_add(self.update_history)
        GLib.idle_add(self.show_chat)
        if not self.settings.get_boolean("welcome-screen-shown"):
            self.first_start()
        self.first_load = False
        self.load_avatar()

    def first_start(self):
        GLib.idle_add(self.show_presentation_window)
        threading.Thread(target=self.install_live2d).start()

    def install_live2d(self):
        try:
            os.makedirs(os.path.join(self.directory, "avatars/live2d"), exist_ok=True)
            os.makedirs(os.path.expanduser("~/.cache/wordllama/tokenizers"), exist_ok=True)
        except Exception as e:
            print(e)
        subprocess.run(['cp', '-a', '/app/data/live2d/web/build', os.path.join(self.directory, "avatars/live2d/web")])

    def show_presentation_window(self):
        self.presentation_dialog = PresentationWindow("presentation", self.settings, self.directory, self)
        self.presentation_dialog.show()

    def mute_tts(self, button):
        if self.tts_enabled:
            self.tts.stop()
        if self.avatar_handler is not None:
            self.avatar_handler.stop()
        button.set_visible(False)


    def start_recording(self, button):
        #button.set_child(Gtk.Spinner(spinning=True))
        button.set_icon_name("media-playback-stop-symbolic")
        button.disconnect_by_func(self.start_recording)
        button.remove_css_class("suggested-action")
        button.add_css_class("error")
        button.connect("clicked", self.stop_recording)
        self.recorder = AudioRecorder()
        t = threading.Thread(target=self.recorder.start_recording)
        t.start()

    def stop_recording(self, button):
        self.recorder.stop_recording(os.path.join(self.directory, "recording.wav"))
        t = threading.Thread(target=self.stop_recording_async, args=(button,))
        t.start()

    def stop_recording_async(self, button):
        button.set_child(None)
        button.set_icon_name("audio-input-microphone-symbolic")
        button.add_css_class("suggested-action")
        button.remove_css_class("error")
        button.disconnect_by_func(self.stop_recording)
        button.connect("clicked", self.start_recording)
        recognizer = self.stt_handler
        result = recognizer.recognize_file(os.path.join(self.directory, "recording.wav"))
        if result is not None:
            self.input_panel.set_text(result)
            self.on_entry_activate(self.input_panel)
        else:
            self.notification_block.add_toast(Adw.Toast(title=_('Could not recognize your voice'), timeout=2))

    def update_settings(self):
        settings = self.settings
        self.offers = settings.get_int("offers")
        self.virtualization = settings.get_boolean("virtualization")
        self.memory = settings.get_int("memory")
        self.hidden_files = settings.get_boolean("hidden-files")
        self.chat_id = settings.get_int("chat")
        self.main_path = settings.get_string("path")
        self.auto_run = settings.get_boolean("auto-run")
        self.chat = self.chats[min(self.chat_id,len(self.chats)-1)]["chat"]
        self.language_model = settings.get_string("language-model")
        self.local_model = settings.get_string("local-model")
        self.tts_enabled = settings.get_boolean("tts-on")
        self.tts_program = settings.get_string("tts")
        self.tts_voice = settings.get_string("tts-voice")
        self.stt_engine = settings.get_string("stt-engine")
        self.stt_settings = settings.get_string("stt-settings") 
        self.external_terminal = settings.get_string("external-terminal")

        # Load extensions
        self.extensionloader = ExtensionLoader(self.extension_path, pip_path=self.pip_directory, extension_cache=self.extensions_cache, settings=self.settings)
        self.extensionloader.load_extensions()
        self.extensionloader.add_handlers(AVAILABLE_LLMS, AVAILABLE_TTS, AVAILABLE_STT)
        self.extensionloader.add_prompts(PROMPTS, AVAILABLE_PROMPTS)
        self.last_avatar_enabled = self.avatar_enabled
        self.avatar_enabled = settings.get_boolean("avatar-on")
        self.translation_enabled = settings.get_boolean("translator-on")
        self.translation_handler = settings.get_string("translator")
        self.smart_prompt_enabled = settings.get_boolean("smart-prompt-on")
        self.smart_prompt_handler = settings.get_string("smart-prompt")

        # Load custom prompts
        self.custom_prompts = json.loads(self.settings.get_string("custom-prompts"))
        self.prompts = override_prompts(self.custom_prompts, PROMPTS)
        self.prompts_settings = json.loads(self.settings.get_string("prompts-settings"))

        if self.language_model in AVAILABLE_LLMS:
            self.model = AVAILABLE_LLMS[self.language_model]["class"](self.settings, os.path.join(self.directory, "models"))
        else:
            mod = list(AVAILABLE_LLMS.values())[0]
            self.model = mod["class"](self.settings, os.path.join(self.directory, "models"))

        # Load handlers and models
        self.model.load_model(self.local_model)
        self.stt_handler = AVAILABLE_STT[self.stt_engine]["class"](self.settings, self.pip_directory)
        
        self.bot_prompts = []
        for prompt in AVAILABLE_PROMPTS:
            is_active = False
            if prompt["setting_name"] in self.prompts_settings:
                is_active = self.prompts_settings[prompt["setting_name"]]
            else:
                is_active = prompt["default"]
            if is_active:
                self.bot_prompts.append(self.prompts[prompt["key"]])

        self.extensions = {}
        if os.path.exists(self.extension_path):
            folder_names = [name for name in os.listdir(self.extension_path) if os.path.isdir(os.path.join(self.extension_path, name))]
            for name in folder_names:
                main_json_path = os.path.join(self.extension_path, name, "main.json")
                if os.path.exists(main_json_path):
                    with open(main_json_path, "r") as file:
                        main_json_data = json.load(file)
                        prompt = main_json_data.get("prompt")
                        name = main_json_data.get("name")
                        status = main_json_data.get("status")
                        api = main_json_data.get("api")
                        if api != None:
                            self.extensions[name] = {"api":api,"status":status,"prompt": prompt}
        if os.path.exists(os.path.expanduser(self.main_path)):
            os.chdir(os.path.expanduser(self.main_path))
        else:
            self.main_path="~"
        if self.tts_program in AVAILABLE_TTS:
            self.tts = AVAILABLE_TTS[self.tts_program]["class"](self.settings, self.directory)
            self.tts.connect('start', lambda : GLib.idle_add(self.mute_tts_button.set_visible, True))
            self.tts.connect('stop', lambda : GLib.idle_add(self.mute_tts_button.set_visible, False))

        if not self.first_load:
            self.load_avatar()


    def load_avatar(self):
        if self.avatar_enabled:
            # If the avatar is enabled, check if it requires reloading
            old_avatar = self.avatar_handler
            selected_key = self.settings.get_string("avatar-model")
            for avatar in AVAILABLE_AVATARS:
                if selected_key == avatar:
                    self.avatar_handler = AVAILABLE_AVATARS[avatar]["class"](self.settings, self.directory)
                    break
            # If it does not require reloading, then just return
            if old_avatar is not None and not old_avatar.requires_reloading(self.avatar_handler) and self.avatar_enabled == self.last_avatar_enabled:
                self.avatar_handler = old_avatar
                return
            # If it requires reloading, reload the old avatar
            self.unload_avatar(old_avatar)
            self.flap_button_avatar.set_visible(True)
            if self.avatar_handler is not None:   
                self.avatar_widget = self.avatar_handler.create_gtk_widget()
                self.boxw.append(self.avatar_widget)
                ReplaceHelper.set_handler(self.avatar_handler)
            else:
                ReplaceHelper.set_handler(None)
        else:
            # If the avatar is disabled, unload the old one and 
            # remove related widgets
            if self.avatar_handler is not None:
                self.unload_avatar(self.avatar_handler)
            self.flap_button_avatar.set_visible(False)
            self.avatar_flap.set_reveal_flap(False)
            self.avatar_flap.set_name("hide")
            return
       
    def unload_avatar(self, handler : AvatarHandler):
        if self.avatar_widget is not None and handler is not None:
            self.boxw.remove(self.avatar_widget)
            handler.destroy()

    def send_button_start_spinner(self):
        spinner = Gtk.Spinner(spinning=True)
        self.send_button.set_child(spinner)

    def remove_send_button_spinner(self):
        self.send_button.set_child(None)
        self.send_button.set_icon_name("go-next-symbolic")

    def on_entry_button_clicked(self,*a):
        self.on_entry_activate(self.input_panel)

    def handle_second_block_change(self,*a):
        status = self.main_program_block.get_reveal_flap()
        if self.main_program_block.get_name()=="hide" and status:
            self.main_program_block.set_reveal_flap(False)
            return True
        elif (self.main_program_block.get_name()=="visible") and (not status):
            self.main_program_block.set_reveal_flap(True)
            return True
        status = self.main_program_block.get_reveal_flap() or self.avatar_flap.get_reveal_flap()
        
        if self.avatar_flap.get_reveal_flap():
            self.chat_panel_header.set_show_end_title_buttons(False)
            self.chat_header.set_show_end_title_buttons(False)
            header_widget = self.web_panel_header
        elif self.main_program_block.get_reveal_flap():
            self.chat_panel_header.set_show_end_title_buttons(False)
            self.chat_header.set_show_end_title_buttons(False)
            header_widget = self.explorer_panel_headerbox
        else:
            self.chat_panel_header.set_show_end_title_buttons(self.main.get_folded())
            self.chat_header.set_show_end_title_buttons(True)
            header_widget = self.chat_header
        # Unparent the headerbox  
        self.headerbox.unparent()
        # Move the headerbox to the right widget
        if type(header_widget) is Adw.HeaderBar or type(header_widget) is Gtk.HeaderBar:
            header_widget.pack_end(self.headerbox)
        elif type(header_widget) is Gtk.Box:
            self.explorer_panel_headerbox.append(self.headerbox)
   
    def on_flap_button_toggled(self, toggle_button):
        self.flap_button_left.set_active(True)
        if self.main_program_block.get_name() == "visible":
            self.main_program_block.set_name("hide")
            self.main_program_block.set_reveal_flap(False)
        else:
            self.main_program_block.set_name("visible")
            self.main_program_block.set_reveal_flap(True)
        if not self.avatar_enabled:
            self.load_avatar()

    def on_avatar_button_toggled(self, toggle_button):
        self.flap_button_avatar.set_active(False)
        if self.avatar_flap.get_name() == "visible":
            self.avatar_flap.set_name("hide")
            self.main_program_block.set_name("hide")
            self.avatar_flap.set_reveal_flap(False)
        else:
            self.avatar_flap.set_name("visible")
            self.avatar_flap.set_reveal_flap(True)
        if not self.avatar_enabled:
            self.load_avatar()
    
    def get_file_button(self, path):
        if path[0:2]=="./":
            path=self.main_path+path[1:len(path)]
        path=os.path.expanduser(os.path.normpath(path))
        button = Gtk.Button(css_classes=["flat"], margin_top=5, margin_start=5, margin_bottom=5, margin_end=5)
        button.connect("clicked", self.run_file_on_button_click)
        button.set_name(path)
        box = Gtk.Box()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        file_name = path.split("/")[-1]
        if os.path.exists(path):
            if os.path.isdir(path):
                name = "folder"
            else:
                if file_name[len(file_name) - 4:len(file_name)] in [".png", ".jpg"]:
                    name = "image-x-generic"
                else:
                    name = "text-x-generic"
        else:
            name = "image-missing"
        icon = Gtk.Image(icon_name=name)
        icon.set_css_classes(["large"])
        box.append(icon)
        box.append(vbox)
        vbox.set_size_request(250, -1)
        vbox.append(Gtk.Label(label=path.split("/")[-1], css_classes=["title-3"], halign=Gtk.Align.START, wrap=True,
                              wrap_mode=Pango.WrapMode.WORD_CHAR))
        vbox.append(Gtk.Label(label='/'.join(path.split("/")[0:-1]), halign=Gtk.Align.START, wrap=True,
                              wrap_mode=Pango.WrapMode.WORD_CHAR))
        button.set_child(box)
        return button

    def run_file_on_button_click(self, button, *a):
        if os.path.exists(button.get_name()):
            if os.path.isdir(os.path.join(os.path.expanduser(self.main_path), button.get_name())):
                self.main_path = button.get_name()
                os.chdir(os.path.expanduser(self.main_path))
                GLib.idle_add(self.update_folder)
            else:
                subprocess.run(['xdg-open', os.path.expanduser(button.get_name())])
        else:
            self.notification_block.add_toast(Adw.Toast(title=_('File not found'), timeout=2))

    def handle_file_drag(self, DropTarget, data, x, y):
        if not self.status:
            self.notification_block.add_toast(Adw.Toast(title=_('The file cannot be sent until the program is finished'), timeout=2))
            return False
        for path in data.split("\n"):
            if os.path.exists(path):
                message_label = self.get_file_button(path)
                if os.path.isdir(path):
                    self.chat.append({"User": "Folder", "Message": " " + path})
                    self.add_message("Folder", message_label)
                else:
                    self.chat.append({"User": "File", "Message": " " + path})
                    self.add_message("File", message_label)
                self.chats[self.chat_id]["chat"] = self.chat
            else:
                self.notification_block.add_toast(Adw.Toast(title=_('The file is not recognized'), timeout=2))

    def go_back_in_explorer_panel(self, *a):
        self.main_path += "/.."
        GLib.idle_add(self.update_folder)

    def go_home_in_explorer_panel(self, *a):
        self.main_path = "~"
        GLib.idle_add(self.update_folder)

    def go_forward_in_explorer_panel(self, *a):
        if self.main_path[len(self.main_path) - 3:len(self.main_path)] == "/..":
            self.main_path = self.main_path[0:len(self.main_path) - 3]
            GLib.idle_add(self.update_folder)

    def go_back_to_chats_panel(self, button):
        self.main.set_visible_child(self.chats_main_box)

    def return_to_chat_panel(self, button):
        self.main.set_visible_child(self.chat_panel)

    def continue_message(self, button):
        if not self.chat[-1]["User"] in ["Assistant","Console","User"]:
            self.notification_block.add_toast(Adw.Toast(title=_('You can no longer continue the message.'), timeout=2))
        else:
            threading.Thread(target=self.send_message).start()
            self.send_button_start_spinner()

    def regenerate_message(self, *a):
        if self.chat[-1]["User"] in ["Assistant","Console"]:
            for i in range(len(self.chat) - 1, -1, -1):
                if self.chat[i]["User"] in ["Assistant","Console"]:
                    self.chat.pop(i)
                else:
                    break
            self.show_chat()
            threading.Thread(target=self.send_message).start()
            self.send_button_start_spinner()
        else:
            self.notification_block.add_toast(Adw.Toast(title=_('You can no longer regenerate the message.'), timeout=2))
    def update_history(self):
        # Update UI
        list_box = Gtk.ListBox(css_classes=["separators","background"])
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.chats_buttons_scroll_block.set_child(list_box)
        for i in range(len(self.chats)):
            box = Gtk.Box(spacing=6, margin_top=3, margin_bottom=3,  margin_start=3, margin_end=3)
            generate_chat_name_button = Gtk.Button(css_classes=["flat", "accent"],
                                                   valign=Gtk.Align.CENTER, icon_name="document-edit-symbolic", width_request=36) # wanted to use: tag-outline-symbolic
            generate_chat_name_button.connect("clicked", self.generate_chat_name)
            generate_chat_name_button.set_name(str(i))

            create_chat_clone_button = Gtk.Button(css_classes=["flat", "success"],
                                                  valign=Gtk.Align.CENTER)
            create_chat_clone_button.connect("clicked", self.copy_chat)
            icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="view-paged-symbolic"))
            icon.set_icon_size(Gtk.IconSize.INHERIT)
            create_chat_clone_button.set_child(icon)
            create_chat_clone_button.set_name(str(i))

            delete_chat_button = Gtk.Button(css_classes=["error","flat"],
                                            valign=Gtk.Align.CENTER)
            delete_chat_button.connect("clicked", self.remove_chat)
            icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="user-trash-symbolic"))
            icon.set_icon_size(Gtk.IconSize.INHERIT)
            delete_chat_button.set_child(icon)
            delete_chat_button.set_name(str(i))
            button = Gtk.Button(css_classes=["flat"], hexpand=True)
            name = self.chats[i]["name"]
            if len(name) > 30:
                #name = name[0:27] + "…"
                button.set_tooltip_text(name)
            button.set_child(Gtk.Label(label=name, wrap=False, wrap_mode=Pango.WrapMode.WORD_CHAR, xalign=0, ellipsize=3, width_chars=22))
            button.set_name(str(i))

            if i == self.chat_id:
                button.connect("clicked", self.return_to_chat_panel)
                delete_chat_button.set_css_classes([""])
                delete_chat_button.set_sensitive(False)
                delete_chat_button.set_can_target(False)
                delete_chat_button.set_has_frame(False)
                button.set_has_frame(True)
            else:
                button.connect("clicked", self.chose_chat)
            list_box.append(box)
            box.append(button)
            box.append(create_chat_clone_button)
            box.append(generate_chat_name_button)
            box.append(delete_chat_button)

    def remove_chat(self, button):
        if int(button.get_name()) < self.chat_id:
            self.chat_id -= 1
        elif int(button.get_name()) == self.chat_id:
            return False
        self.chats.pop(int(button.get_name()))
        self.update_history()

    def generate_chat_name(self, button, multithreading=False):
        if multithreading:
            if len(self.chats[int(button.get_name())]["chat"]) < 2:
                self.notification_block.add_toast(Adw.Toast(title=_('Chat is empty'), timeout=2))
                return False
            spinner = Gtk.Spinner(spinning=True)
            button.set_child(spinner)
            button.set_can_target(False)
            button.set_has_frame(True)
            # TODO: take the history for the correct chat
            self.model.set_history([], self)
            name = self.model.generate_chat_name(self.prompts["generate_name_prompt"])
            if name != "Chat has been stopped":
                self.chats[int(button.get_name())]["name"] = name
            self.update_history()
        else:
            threading.Thread(target=self.generate_chat_name, args=[button, True]).start()

    def new_chat(self, button, *a):
        self.chats.append({"name": _("Chat ")+str(len(self.chats) + 1), "chat": []})
        self.update_history()

    def copy_chat(self, button, *a):
        self.chats.append({"name":self.chats[int(button.get_name())]["name"],"chat":self.chats[int(button.get_name())]["chat"][:]})
        self.update_history()

    def chose_chat(self, button, *a):
        self.main.set_visible_child(self.chat_panel)
        if not self.status:
            self.stop_chat()
        self.stream_number_variable += 1
        self.chat_id = int(button.get_name())
        self.chat = self.chats[self.chat_id]["chat"]
        self.update_history()
        self.show_chat()
        GLib.idle_add(self.update_button_text)

    def scrolled_chat(self):
        adjustment = self.chat_scroll.get_vadjustment()
        value = adjustment.get_upper()
        adjustment.set_value(100000)

    def create_table(self, table):
        data = []
        for row in table:
            cells = row.strip('|').split('|')
            data.append([cell.strip() for cell in cells])
        model = Gtk.ListStore(*[str] * len(data[0]))
        for row in data[1:]:
            if not all(element == "-" * len(element) for element in row):
                model.append(row)
        self.treeview = Gtk.TreeView(model=model, css_classes=["toolbar", "view", "transparent"])

        for i, title in enumerate(data[0]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            self.treeview.append_column(column)
        return self.treeview

    def clear_chat(self, button):
        self.notification_block.add_toast(Adw.Toast(title=_('Chat is cleared'), timeout=2))
        self.chat = []
        self.chats[self.chat_id]["chat"] = self.chat
        self.show_chat()
        self.stream_number_variable += 1
        threading.Thread(target=self.update_button_text).start()

    def stop_chat(self, button=None):
        self.status = True
        self.stream_number_variable += 1
        self.chat_stop_button.set_visible(False)
        GLib.idle_add(self.update_button_text)
        if self.chat[-1]["User"] != "Assistant" or "```console" in self.chat[-1]["Message"]:
            for i in range(len(self.chat) - 1, -1, -1):
                if self.chat[i]["User"] in ["Assistant","Console"]:
                    self.chat.pop(i)
                else:
                    break
        self.notification_block.add_toast(Adw.Toast(title=_('The message was canceled and deleted from history'), timeout=2))
        self.show_chat()
        self.remove_send_button_spinner()

    def send_message_to_bot(self, message):
        return self.model.send_message(self, message)


    def send_bot_response(self, button):
        self.send_button_start_spinner()
        text = button.get_child().get_label()
        self.chat.append({"User": "User", "Message": " "+text})
        message_label = Gtk.Label(label=text, margin_top=10, margin_start=10, margin_bottom=10, margin_end=10, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                  selectable=True)
        self.add_message("User", message_label, len(self.chat) - 1)
        threading.Thread(target=self.send_message).start()

    def update_folder(self, *a):
        if not self.check_streams["folder"]:
            self.check_streams["folder"] = True
            if os.path.exists(os.path.expanduser(self.main_path)):
                self.explorer_panel_header.set_title_widget(Gtk.Label(label=os.path.normpath(self.main_path)+(3-len(os.path.normpath(self.main_path)))*" ", css_classes=["title"],ellipsize=Pango.EllipsizeMode.MIDDLE,max_width_chars=15,halign=Gtk.Align.CENTER,hexpand=True))
                if len(os.listdir(os.path.expanduser(self.main_path))) == 0 or (sum(
                        1 for filename in os.listdir(os.path.expanduser(self.main_path)) if
                        not filename.startswith('.')) == 0 and not self.hidden_files) and os.path.normpath(self.main_path) != "~":
                    self.explorer_panel.remove(self.folder_blocks_panel)
                    self.folder_blocks_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20, opacity=0.25)
                    self.explorer_panel.append(self.folder_blocks_panel)
                    icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="folder-symbolic"))
                    icon.set_css_classes(["empty-folder"])
                    icon.set_valign(Gtk.Align.END)
                    icon.set_vexpand(True)
                    self.folder_blocks_panel.append(icon)
                    self.folder_blocks_panel.append(Gtk.Label(label=_("Folder is Empty"), wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, vexpand=True,valign=Gtk.Align.START,css_classes=["empty-folder", "heading"]))
                else:
                    self.explorer_panel.remove(self.folder_blocks_panel)
                    self.folder_blocks_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    self.explorer_panel.append(self.folder_blocks_panel)

                    flow_box = Gtk.FlowBox(vexpand=True)
                    flow_box.set_valign(Gtk.Align.START)

                    if os.path.normpath(self.main_path) == "~":
                        os.chdir(os.path.expanduser("~"))
                        path = "./.var/app/moe.nyarchlinux.assistant/NyarchAssistant"
                        if not os.path.exists(path):
                            os.makedirs(path)
                        button = Gtk.Button(css_classes=["flat"])
                        button.set_name(".var/app/moe.nyarchlinux.assistant/NyarchAssistant")
                        button.connect("clicked", self.open_folder)

                        icon = File(self.main_path, ".var/app/moe.nyarchlinux.assistant/NyarchAssistant")
                        icon.set_css_classes(["large"])
                        icon.set_valign(Gtk.Align.END)
                        icon.set_vexpand(True)
                        file_label = Gtk.Label(label="NyarchAssistant", wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                               vexpand=True, max_width_chars=11, valign=Gtk.Align.START,
                                               ellipsize=Pango.EllipsizeMode.MIDDLE)
                        file_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                        file_box.append(icon)
                        file_box.set_size_request(110, 110)
                        file_box.append(file_label)
                        button.set_child(file_box)

                        flow_box.append(button)
                    for file_info in os.listdir(os.path.expanduser(self.main_path)):
                        if file_info[0] == "." and not self.hidden_files:
                            continue
                        button = Gtk.Button(css_classes=["flat"])
                        button.set_name(file_info)
                        button.connect("clicked", self.open_folder)

                        icon = File(self.main_path, file_info)
                        icon.set_css_classes(["large"])
                        icon.set_valign(Gtk.Align.END)
                        icon.set_vexpand(True)
                        file_label = Gtk.Label(label=file_info+" "*(5-len(file_info)), wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                               vexpand=True, max_width_chars=11, valign=Gtk.Align.START,
                                               ellipsize=Pango.EllipsizeMode.MIDDLE)
                        file_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                        file_box.append(icon)
                        file_box.set_size_request(110, 110)
                        file_box.append(file_label)
                        button.set_child(file_box)

                        flow_box.append(button)
                    scrolled_window = Gtk.ScrolledWindow()
                    scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                    scrolled_window.set_child(flow_box)
                    self.folder_blocks_panel.append(scrolled_window)
            else:
                self.main_path = "~"
                self.update_folder()
            self.check_streams["folder"]=False
    def get_target_directory(self,working_directory, directory):
        try:
            directory = directory.strip()
            if directory.startswith("'") and directory.endswith("'"):
                directory = directory[1:-1]
            elif directory.startswith('"') and directory.endswith('"'):
                directory = directory[1:-1]

            if directory.startswith("~"):
                directory = os.path.expanduser("~") + directory[1:]

            target_directory = posixpath.join(working_directory, directory)
            return (True, os.path.normpath(target_directory))
        except (IndexError, OSError) as e:
            return (False,working_directory)
    def open_folder(self, button, *a):
        if os.path.exists(os.path.join(os.path.expanduser(self.main_path), button.get_name())):
            if os.path.isdir(os.path.join(os.path.expanduser(self.main_path), button.get_name())):
                self.main_path += "/" + button.get_name()
                os.chdir(os.path.expanduser(self.main_path))
                GLib.idle_add(self.update_folder)
            else:
                subprocess.run(['xdg-open', os.path.expanduser(self.main_path + "/" + button.get_name())])
        else:
            self.notification_block.add_toast(Adw.Toast(title=_('File not found'), timeout=2))
    def handle_main_block_change(self, *data):
        if (self.main.get_folded()):
            self.chat_panel_header.set_show_end_title_buttons(not self.main_program_block.get_reveal_flap())
            self.left_panel_back_button.set_visible(True)
        else:
            self.chat_panel_header.set_show_end_title_buttons(False)
            self.left_panel_back_button.set_visible(False)

    def execute_terminal_command(self, command):
        os.chdir(os.path.expanduser(self.main_path))
        console_permissions = ""
        if not self.virtualization:
            console_permissions = "flatpak-spawn --host"
        commands = ('\n'.join(command)).split(" && ")
        txt = ""
        path=self.main_path
        for t in commands:
            if txt!="":
                txt+=" && "
            if "cd " in t:
                txt+=t
                p = (t.split("cd "))[min(len(t.split("cd ")),1)]
                v = self.get_target_directory(path, p)
                if not v[0]:
                    Adw.Toast(title=_('Wrong folder path'), timeout=2)
                else:
                    path = v[1]
            else:
                txt+=console_permissions+" "+t
        process = subprocess.Popen(txt, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, shell=True)
        outputs = []

        def read_output(process, outputs):
            try:
                stdout, stderr = process.communicate()
                if process.returncode != 0:
                    outputs.append((False, stderr.decode()))
                else:
                    if stdout.decode() == "":
                        outputs.append((True, "Done"))
                    outputs.append((True, stdout.decode()))
            except Exception as e:
                pass

        output_thread = threading.Thread(target=read_output, args=(process, outputs))
        output_thread.start()
        for i in range(5):
            time.sleep(i)
            if outputs!=[]:
                break
        else:
            self.streams.append(process)
            outputs = [(True, _("Thread has not been completed, thread number: ")+str(len(self.streams)))]
        if os.path.exists(os.path.expanduser(path)):
            os.chdir(os.path.expanduser(path))
            self.main_path = path
            GLib.idle_add(self.update_folder)
        else:
            Adw.Toast(title=_('Failed to open the folder'), timeout=2)
        if len(outputs[0][1]) > 1000:
            new_value = outputs[0][1][0:1000] + "..."
            outputs = ((outputs[0][0], new_value),)
        return outputs[0]


    def get_chat(self, chat):
        chats = ""
        for c in chat:
            chats += "\n" + c["User"] + ":" + c["Message"]
        return chats

    def update_button_text(self):
        stream_number_variable = self.stream_number_variable
        message_suggestion_texts_array = []
        for btn in self.message_suggestion_buttons_array:
            btn.set_visible(False)
        self.button_clear.set_visible(False)
        self.button_continue.set_visible(False)
        self.regenerate_message_button.set_visible(False)
        self.chat_stop_button.set_visible(False)
        if self.status:
            if self.chat != []:
                self.button_clear.set_visible(True)
                if self.chat[-1]["User"] in ["Assistant","Console"]:
                    self.regenerate_message_button.set_visible(True)
                elif self.chat[-1]["User"] in ["Assistant","Console","User"]:
                    self.button_continue.set_visible(True)
            # Generate suggestions in another thread and then add them to the UI
            threading.Thread(target=self.generate_suggestions).start()
        else:
            for btn in self.message_suggestion_buttons_array:
                btn.set_visible(False)
            self.button_clear.set_visible(False)
            self.button_continue.set_visible(False)
            self.regenerate_message_button.set_visible(False)
            self.chat_stop_button.set_visible(True)
        GLib.idle_add(self.scrolled_chat)

    def generate_suggestions(self):
        """Create the suggestions and update the UI when it's finished"""
        suggestions = self.model.get_suggestions(self.prompts["get_suggestions_prompt"], self.offers)
        GLib.idle_add(self.populate_suggestions, suggestions)

    def populate_suggestions(self, suggestions):
        """Update the UI with the generated suggestions"""
        i = 0
        # Convert to tuple to remove duplicates
        for suggestion in tuple(suggestions):
            if i+1 > self.offers:
                break
            else:
                message = suggestion.replace("\n","")
                btn = self.message_suggestion_buttons_array[i]
                btn.get_child().set_label(message)
                btn.set_visible(True)
                GLib.idle_add(self.scrolled_chat)
            i+=1
        self.chat_stop_button.set_visible(False)
        GLib.idle_add(self.scrolled_chat)

    def on_entry_activate(self, entry):
        if not self.status:
            self.notification_block.add_toast(
                Adw.Toast(title=_('The message cannot be sent until the program is finished'), timeout=2))
            return False
        text = entry.get_text()
        entry.set_text('')
        if not text == " " * len(text):
            self.chat.append({"User": "User", "Message": " " + text})
            message_label = Gtk.Label(label=text, margin_top=10, margin_start=10, margin_bottom=10, margin_end=10,
                                      wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, selectable=True)
            self.add_message("User", message_label, len(self.chat) - 1)
        self.scrolled_chat()
        threading.Thread(target=self.send_message).start()
        self.send_button_start_spinner()

    def show_chat(self):
        if not self.check_streams["chat"]:
            self.check_streams["chat"] = True
            try:
                self.chat_scroll_window.remove(self.chat_list_block)
                self.chat_list_block = Gtk.ListBox(css_classes=["separators","background","view"])
                self.chat_list_block.set_selection_mode(Gtk.SelectionMode.NONE)

                self.chat_scroll_window.append(self.chat_list_block)
            except Exception as e:
                self.notification_block.add_toast(Adw.Toast(title=e))

            self.chat_scroll_window.remove(self.chat_controls_entry_block)
            self.chat_scroll_window.remove(self.offers_entry_block)
            self.chat_scroll_window.append(self.chat_controls_entry_block)
            self.chat_scroll_window.append(self.offers_entry_block)
            if not self.virtualization:
                self.add_message("WarningNoVirtual")
            else:
                self.add_message("Disclaimer")
            for i in range(len(self.chat)):
                if self.chat[i]["User"] == "User":
                    self.add_message("User", Gtk.Label(label=self.chat[i]["Message"][1:len(self.chat[i]["Message"])], margin_top=10, margin_start=10,
                                                       margin_bottom=10, margin_end=10, wrap=True,
                                                       wrap_mode=Pango.WrapMode.WORD_CHAR, selectable=True), i)
                elif self.chat[i]["User"] == "Assistant":
                    self.show_message(self.chat[i]["Message"], True, id_message=i)
                elif self.chat[i]["User"] in ["File", "Folder"]:
                    self.add_message(self.chat[i]["User"], self.get_file_button(self.chat[i]["Message"][1:len(self.chat[i]["Message"])]))
            self.check_streams["chat"] = False
        GLib.idle_add(self.scrolled_chat)

    def show_message(self, message_label, restore=False,id_message=-1):
        if message_label == " " * len(message_label):
            if not restore:
                self.chat.append({"User": "Assistant", "Message": message_label})
                GLib.idle_add(self.update_button_text)
                self.status = True
                self.chat_stop_button.set_visible(False)
        else:
            if not restore: self.chat.append({"User": "Assistant", "Message": message_label})
            table_string = message_label.split("\n")
            box = Gtk.Box(margin_top=10, margin_start=10, margin_bottom=10, margin_end=10,
                          orientation=Gtk.Orientation.VERTICAL)
            start_table_index = -1
            table_length = 0
            code_language = ""
            start_code_index = -1
            has_terminal_command = False
            running_threads = []
            for i in range(len(table_string)):
                if len(table_string[i]) > 0 and table_string[i].lstrip(" ")[0:3] == "```":
                    table_string[i] = table_string[i].lstrip(" ")
                    if start_code_index == -1:
                        start_code_index = i + 1
                        code_language = table_string[i][3:len(table_string[i])]
                    else:
                        if code_language in self.extensionloader.codeblocks:
                            
                            value = '\n'.join(table_string[start_code_index:i])
                            extension = self.extensionloader.codeblocks[code_language]
                            try:
                                widget = extension.get_gtk_widget(value, code_language)
                                if widget is not None:
                                    box.append(widget)
                                else:

                                    if id_message==-1:
                                        id_message = len(self.chat)-1
                                    id_message+=1
                                    has_terminal_command = True
                                    text_expander = Gtk.Expander(
                                        label=code_language, css_classes=["toolbar", "osd"], margin_top=10, margin_start=10,
                                        margin_bottom=10, margin_end=10
                                    )
                                    text_expander.set_expanded(False)
                                    reply_from_the_console = None
                                    if self.chat[min(id_message, len(self.chat) - 1)]["User"] == "Console":
                                        reply_from_the_console = self.chat[min(id_message, len(self.chat) - 1)]["Message"]
                                    def getresponse():
                                        if not restore:
                                            response = extension.get_answer(value, code_language)  
                                            if response is not None:
                                                code = (True, response)
                                            else:
                                                code = (False, "Error:") 
                                        else:
                                            code = (True, reply_from_the_console)
                                        text_expander.set_child(
                                            Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, label='\n'.join(table_string[start_code_index:i])+"\n"+str(code[1]),
                                                      selectable=True))
                                        if not code[0]:
                                            self.add_message("Error", text_expander)
                                        elif restore:
                                            self.add_message("Assistant", text_expander)
                                        else:
                                            self.add_message("Done", text_expander)
                                        if not restore:
                                            self.chat.append({"User": "Console", "Message": " " + code[1]})
                                          
                                    t = threading.Thread(target=getresponse)
                                    t.start()
                                    running_threads.append(t)
                            except Exception as e:
                                print("Extension error " + extension.id + ": " + str(e))
                                box.append(CopyBox("\n".join(table_string[start_code_index:i]), code_language, parent = self))
                        elif code_language == "image":
                            for i in table_string[start_code_index:i]:
                                image = Gtk.Image(css_classes=["image"])
                                image.set_from_file(i)
                                box.append(image)

                        elif code_language == "console":
                            if id_message==-1:
                                id_message = len(self.chat)-1
                            id_message+=1
                            if self.auto_run and not any(command in "\n".join(table_string[start_code_index:i]) for command in ["rm ","apt ","sudo ","yum ","mkfs "]):
                                has_terminal_command = True
                                value = table_string[start_code_index:i]
                                text_expander = Gtk.Expander(
                                    label="Console", css_classes=["toolbar", "osd"], margin_top=10, margin_start=10,
                                    margin_bottom=10, margin_end=10
                                )
                                text_expander.set_expanded(False)
                                path=""
                                reply_from_the_console = None
                                if self.chat[min(id_message, len(self.chat) - 1)]["User"] == "Console":
                                    reply_from_the_console = self.chat[min(id_message, len(self.chat) - 1)]["Message"]
                                if not restore:
                                    path=os.path.normpath(self.main_path)
                                    code = self.execute_terminal_command(value)
                                else:
                                    code = (True, reply_from_the_console)
                                val='\n'.join(value)
                                text = f"[User {path}]:$ {val}\n{code[1]}"
                                text_expander.set_child(
                                    Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, label=text,
                                              selectable=True))
                                if not code[0]:
                                    self.add_message("Error", text_expander)
                                elif restore:
                                    self.add_message("Assistant", text_expander)
                                else:
                                    self.add_message("Done", text_expander)
                                if not restore:
                                    self.chat.append({"User": "Console", "Message": " " + code[1]})
                            else:
                                if not restore:
                                    self.chat.append({"User": "Console", "Message": f"None"})
                                box.append(CopyBox("\n".join(table_string[start_code_index:i]), code_language, self,id_message))
                            result = {}
                        elif code_language in ["file", "folder"]:
                            for obj in table_string[start_code_index:i]:
                                box.append(self.get_file_button(obj))
                        elif code_language == "chart":
                            result = {}
                            lines = table_string[start_code_index:i]
                            for line in lines:
                                parts = line.split('-')
                                if len(parts) == 2:
                                    key = parts[0].strip()
                                    percentages = "%" in parts[1]
                                    value = ''.join(filter(lambda x: x.isdigit() or x==".", parts[1]))
                                    result[key] = float(value)
                                else:
                                    box.append(CopyBox("\n".join(table_string[start_code_index:i]), code_language, parent = self))
                                    result = {}
                                    break
                            if result !={}:
                                box.append(BarChartBox(result,percentages))
                        else:
                            box.append(CopyBox("\n".join(table_string[start_code_index:i]), code_language, parent = self))
                        start_code_index = -1
                elif len(table_string[i]) > 0 and table_string[i][0] == "|":
                    if start_table_index == -1:
                        table_length = len(table_string[i].split("|"))
                        start_table_index = i
                    elif table_length != len(table_string[i].split("|")):

                        box.append(self.create_table(table_string[start_table_index:i]))
                        start_table_index = i
                elif start_table_index != -1:
                    box.append(self.create_table(table_string[start_table_index:i-1]))
                    start_table_index = -1
                elif start_code_index == -1:
                    label = markwon_to_pango(table_string[i])
                    box.append(Gtk.Label(label=label, wrap=True, halign=Gtk.Align.START,
                                         wrap_mode=Pango.WrapMode.WORD_CHAR, width_chars=1, selectable=True, use_markup=True))
            if start_table_index != -1:
                box.append(self.create_table(table_string[start_table_index:len(table_string)]))
            if not has_terminal_command:
                self.add_message("Assistant", box)
                if not restore:
                    GLib.idle_add(self.update_button_text)
                    self.status = True
                    self.chat_stop_button.set_visible(False)
                    self.chats[self.chat_id]["chat"] = self.chat
            else:
                if not restore:
                    def wait_threads_sm():
                        for t in running_threads:
                            t.join()
                        GLib.idle_add(self.send_message)
                    threading.Thread(target=wait_threads_sm).start()
        GLib.idle_add(self.scrolled_chat)
        self.save_chat()

    def get_history(self) -> list[dict[str, str]]: 
        history = []
        count = self.memory
        for msg in self.chat[:-1]:
            if count == 0:
                break
            if msg["User"] == "Console" and msg["Message"] == "None":
                continue
            history.append(msg)
            count -= 1
        return history

    def send_message(self):
        self.stream_number_variable += 1
        stream_number_variable = self.stream_number_variable
        self.status = False
        self.update_button_text()

        # Append extensions prompts
        prompts = [replace_variables(value["prompt"]) for value in self.extensions.values() if value["status"]]
        
        for prompt in self.bot_prompts:
            prompts.append(replace_variables(prompt))
       
        # Get smart prompts
        if self.smart_prompt_enabled:
            if self.smart_prompt_handler in AVAILABLE_SMART_PROMPTS:
                try:
                    smart_prompt = AVAILABLE_SMART_PROMPTS[self.smart_prompt_handler]["class"](self.settings, self.directory)
                    generated = smart_prompt.get_extra_prompts(self.chat[-1]["Message"], self.get_history(), EXTRA_PROMPTS)
                    prompts += generated
                except Exception as e:
                    print(e)

        # Set history and prompts
        self.model.set_history(prompts, self.get_history())
        if self.model.stream_enabled():
            label = Gtk.Label(label="", margin_top=10, margin_start=10, margin_bottom=10, margin_end=10, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                  selectable=True)
            box=self.add_message("Assistant",label)
            message_label = self.model.send_message_stream(self, self.chat[-1]["Message"], self.update_message, (label, ))
            try:
                box.get_parent().set_visible(False)
            except:
                pass
        else:
            message_label = self.send_message_to_bot(self.chat[-1]["Message"])
        
        if self.stream_number_variable == stream_number_variable:
            GLib.idle_add(self.show_message, message_label)
        GLib.idle_add(self.remove_send_button_spinner)
        # TTS
        if self.tts_enabled:
            if self.tts_program in AVAILABLE_TTS:
                # Remove text in *text*
                message = re.sub(r"\*(.*?)\*", "", message_label)
                message = re.sub(r"```.*?```", "", message, flags=re.DOTALL)
                # Remove text in *text*
                if not(not message.strip() or message.isspace() or all(char == '\n' for char in message)):
                    # Translate the message
                    translator = None
                    if self.translation_enabled and self.translation_handler in AVAILABLE_TRANSLATORS:
                        translator = AVAILABLE_TRANSLATORS[self.translation_handler]["class"](self.settings, self.directory)          
                    if self.avatar_enabled and self.avatar_handler is not None:
                        self.avatar_handler.speak_with_tts(message, self.tts, translator)
                    else:
                        if translator is not None:
                            message = translator.translate(message)
                        threading.Thread(target=self.tts.play_audio, args=(message, )).start() 

    def update_message(self, message, label):    
        GLib.idle_add(label.set_label, message)

    def edit_message(self, gesture, data, x, y):
        if not self.status:
            self.notification_block.add_toast(Adw.Toast(title=_("You can't edit a message while the program is running."), timeout=2))
            return False
        self.input_panel.set_text(self.chat[int(gesture.get_name())]["Message"])
        self.input_panel.grab_focus()
        self.chats.append({"name": self.chats[self.chat_id]["name"], "chat": self.chat[0:int(gesture.get_name())]})
        self.stream_number_variable += 1
        self.chats[self.chat_id]["chat"] = self.chat
        self.chat_id = len(self.chats) - 1
        self.chat = self.chats[self.chat_id]["chat"]
        self.update_history()
        self.show_chat()
        GLib.idle_add(self.update_button_text)

    def add_message(self, user, message=None, id_message=0):
        box = Gtk.Box(css_classes=["card"], margin_top=10, margin_start=10, margin_bottom=10, margin_end=10,
                      halign=Gtk.Align.START)
        if user == "User":
            evk = Gtk.GestureClick.new()
            evk.connect("pressed", self.edit_message)
            evk.set_name(str(id_message))
            evk.set_button(3)
            box.add_controller(evk)
            box.append(Gtk.Label(label=user + ": ", margin_top=10, margin_start=10, margin_bottom=10, margin_end=0,
                                 css_classes=["accent", "heading"]))
            box.set_css_classes(["card", "user"])
        if user == "Assistant":
            box.append(Gtk.Label(label=user + ": ", margin_top=10, margin_start=10, margin_bottom=10, margin_end=0,
                                 css_classes=["warning", "heading"]))
            box.set_css_classes(["card", "assistant"])
        if user == "Done":
            box.append(Gtk.Label(label="Assistant: ", margin_top=10, margin_start=10, margin_bottom=10, margin_end=0,
                                 css_classes=["success", "heading"]))
            box.set_css_classes(["card", "done"])
        if user == "Error":
            box.append(Gtk.Label(label="Assistant: ", margin_top=10, margin_start=10, margin_bottom=10, margin_end=0,
                                 css_classes=["error", "heading"]))
            box.set_css_classes(["card", "failed"])
        if user == "File":
            box.append(Gtk.Label(label="User: ", margin_top=10, margin_start=10, margin_bottom=10, margin_end=0,
                                 css_classes=["accent", "heading"]))
            box.set_css_classes(["card", "file"])
        if user == "Folder":
            box.append(Gtk.Label(label="User: ", margin_top=10, margin_start=10, margin_bottom=10, margin_end=0,
                                 css_classes=["accent", "heading"]))
            box.set_css_classes(["card", "folder"])
        if user == "WarningNoVirtual":
            icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="dialog-warning"))
            icon.set_icon_size(Gtk.IconSize.LARGE)
            icon.set_properties(margin_top=10, margin_start=20, margin_bottom=10, margin_end=10)
            box_warning = Gtk.Box(halign=Gtk.Align.CENTER, orientation=Gtk.Orientation.HORIZONTAL,
                                  css_classes=["warning", "heading"])
            box_warning.append(icon)

            label = Gtk.Label(
                label=_("The neural network has access to your computer and any data in this chat and can run commands, be careful, we are not responsible for the neural network. Do not share any sensitive information."),
                margin_top=10, margin_start=10, margin_bottom=10, margin_end=10, wrap=True,
                wrap_mode=Pango.WrapMode.WORD_CHAR)

            box_warning.append(label)
            box.append(box_warning)
            box.set_halign(Gtk.Align.CENTER)
            box.set_css_classes(["card", "message-warning"])
        elif user == "Disclaimer":
            icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="user-info-symbolic"))
            icon.set_icon_size(Gtk.IconSize.LARGE)
            icon.set_properties(margin_top=10, margin_start=20, margin_bottom=10, margin_end=10)
            box_warning = Gtk.Box(halign=Gtk.Align.CENTER, orientation=Gtk.Orientation.HORIZONTAL,
                                  css_classes=["heading"])
            box_warning.append(icon)

            label = Gtk.Label(
                label=_("The neural network has access to any data in this chat, be careful, we are not responsible for the neural network. Do not share any sensitive information."),
                margin_top=10, margin_start=10, margin_bottom=10, margin_end=10, wrap=True,
                wrap_mode=Pango.WrapMode.WORD_CHAR)

            box_warning.append(label)
            box.append(box_warning)
            box.set_halign(Gtk.Align.CENTER)
            box.set_css_classes(["card"])
        else:
            box.append(message)
        self.chat_list_block.append(box)
        return box

    def save_chat(self):
        prevdir = os.getcwd()
        os.chdir(os.path.expanduser("~"))
        with open(self.path + self.filename, 'wb') as f:
            pickle.dump(self.chats, f)
        os.chdir(prevdir)


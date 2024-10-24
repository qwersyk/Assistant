from threading import Thread
import gi, os

from .constants import AVAILABLE_LLMS, AVAILABLE_PROMPTS, AVAILABLE_STT, AVAILABLE_TTS, PROMPTS

from .extensions import ExtensionLoader
from gi.repository import Gtk, Adw, Gio, GLib


class Extension(Gtk.Window):
    def __init__(self,app):
        Gtk.Window.__init__(self, title=_("Extensions"))
        self.path = os.path.expanduser("~")+"/.var/app/moe.nyarchlinux.assistant/extension"

        self.directory = GLib.get_user_config_dir()
        self.path = os.path.join(self.directory, "extensions")
        self.pip_directory = os.path.join(self.directory, "pip")
        self.extension_path = os.path.join(self.directory, "extensions")
        self.extensions_cache = os.path.join(self.directory, "extensions_cache")
                
        self.app = app
        self.set_default_size(500, 500)
        self.set_transient_for(app.win)
        self.set_modal(True)
        self.set_titlebar(Adw.HeaderBar(css_classes=["flat"]))

        self.notification_block = Adw.ToastOverlay()
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.notification_block.set_child(self.scrolled_window)

        self.set_child(self.notification_block)
        self.update()
    
    def update(self):
        self.main = Gtk.Box(margin_top=10,margin_start=10,margin_bottom=10,margin_end=10,valign=Gtk.Align.FILL,halign=Gtk.Align.CENTER,orientation=Gtk.Orientation.VERTICAL)
        self.main.set_size_request(300, -1)
        self.scrolled_window.set_child(self.main)
        self.extensionloader = ExtensionLoader(self.extension_path, pip_path=self.pip_directory, extension_cache=self.extensions_cache, settings=self.settings)
        self.extensionloader.load_extensions()

        for extension in self.extensionloader.get_extensions():
            box = Gtk.Box(margin_top=10,margin_bottom=10,css_classes=["card"], hexpand=True)
            box.append(Gtk.Label(label=f"{extension.name}",margin_top=10,margin_start=10,margin_end=10,margin_bottom=10))
            box_elements = Gtk.Box(valign=Gtk.Align.CENTER,halign=Gtk.Align.END, hexpand= True)
            button = Gtk.Button(css_classes=["flat"], margin_top=10,margin_start=10,margin_end=10,margin_bottom=10)
            button.connect("clicked", self.delete_extension)
            button.set_name(extension.id)

            icon_name="user-trash-symbolic"
            icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name=icon_name))
            icon.set_icon_size(Gtk.IconSize.INHERIT)
            button.set_child(icon)
            switch = Gtk.Switch(valign=Gtk.Align.CENTER)
            switch.connect("notify::state", self.change_status)
            switch.set_name(extension.id)
            switch.set_active(extension not in self.extensionloader.disabled_extensions)
            box_elements.append(switch)
            box_elements.append(button)
            box.append(box_elements)
            self.main.append(box)
        folder_button = Gtk.Button(label=_("Choose an extension"), css_classes=["suggested-action"], margin_top=10)
        folder_button.connect("clicked", self.on_folder_button_clicked)
        self.main.append(folder_button)
    
    def change_status(self,widget,*a):        
        name = widget.get_name()
        if widget.get_active():
            self.extensionloader.enable(name)
        else:
            self.extensionloader.disable(name)
            self.extensionloader.remove_handlers(self.extensionloader.get_extension_by_id(name), AVAILABLE_LLMS, AVAILABLE_TTS, AVAILABLE_STT)
            self.extensionloader.remove_prompts(self.extensionloader.get_extension_by_id(name), PROMPTS, AVAILABLE_PROMPTS)
    def delete_extension(self,widget):
        self.extensionloader.remove_extension(widget.get_name())
        self.update()
    
    def on_folder_button_clicked(self, widget):
        dialog = Gtk.FileChooserNative(transient_for=self.app.win, title=_("Add extension"), modal=True, action=Gtk.FileChooserAction.OPEN)
        dialog.connect("response", self.process_folder)
        dialog.show()
    
    def process_folder(self, dialog, response):
        if response != Gtk.ResponseType.ACCEPT:
            dialog.destroy()
            return False

        file=dialog.get_file()
        if file == None:
            return True
        file_path = file.get_path()
        self.extensionloader.add_extension(file_path)
        self.extensionloader.load_extensions()

        for extid, filename in self.extensionloader.filemap.items():
            if filename == os.path.basename(file_path):
                ext = self.extensionloader.get_extension_by_id(extid)
                if ext is None:
                    continue
                Thread(target=ext.install).start()
                break
        
        if os.path.basename(file_path) in self.extensionloader.filemap.values():
            self.notification_block.add_toast(Adw.Toast(title=(_("Extension added. New extensions will run"))))
            self.extensionloader.load_extensions()
            self.update()
        else:
            self.notification_block.add_toast(Adw.Toast(title=_("This is not an extension or it is not correct")))

        dialog.destroy()
        return False


from gi.repository import Gtk, Gio, GLib, Gdk
import matplotlib.pyplot as plt
import uuid
import os 

class DisplayLatex(Gtk.Box):
    cachedir = GLib.get_user_data_dir()
 
    def __init__(self, latex:str, size:int) -> None:
        super().__init__()
        self.size = size
        overlay = Gtk.Overlay() 
        color = self.get_style_context().lookup_color("window_fg_color")[1]
        id = latex + str(size) + str(color.red) + str(color.green) + str(color.blue)

        self.latex = latex 
# Create equation image
        plt.figure()
        plt.text(0.5, 0.5, r'$' + latex + r'$', fontsize=size, ha='center', va='center', color=(color.red, color.blue, color.green)) 
        plt.axis('off')
# Get file name and save it in the cache
        fname = os.path.join(self.cachedir, uuid.uuid4().hex + '-symbolic.svg')

        plt.tight_layout(pad=0)
        plt.savefig(fname, transparent=True, bbox_inches='tight', pad_inches=0)
# Create Gtk.Picture
        self.picture = Gtk.Picture()
        self.picture.set_file(Gio.File.new_for_path(fname)) 
        self.picture.set_size_request(-1, size)
        self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        plt.close()

        self.create_control_box()
        self.controller()
        overlay.set_child(self.picture)
        overlay.add_overlay(self.control_box)
        self.append(overlay)


    def zoom_in(self, *_):
        self.size += 10
        self.picture.set_size_request(-1, self.size)
    
    def zoom_out(self, *_):
        if self.size < 20:
            return
        self.size -= 10
        self.picture.set_size_request(-1, self.size)

    def create_control_box(self):
        self.control_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, halign=Gtk.Align.END, css_classes=["flat"], visible=False)
        self.copy_button = Gtk.Button(halign=Gtk.Align.START, css_classes=["flat", "accent"], icon_name="edit-copy-symbolic", valign=Gtk.Align.START)
        self.copy_button.connect("clicked", self.copy_button_clicked)
        
        self.zoom_out_button = Gtk.Button(halign=Gtk.Align.START, css_classes=["flat", "error"], icon_name="zoom-out-symbolic", valign=Gtk.Align.START)
        self.zoom_out_button.connect("clicked", self.zoom_out)
        self.control_box.append(self.zoom_out_button)
        
        self.zoom_in_button = Gtk.Button(halign=Gtk.Align.START, css_classes=["flat", "success"], icon_name="zoom-in-symbolic", valign=Gtk.Align.START)
        self.zoom_in_button.connect("clicked", self.zoom_in)
        self.control_box.append(self.zoom_in_button)


        self.control_box.append(self.copy_button)


    def controller(self):
        ev = Gtk.EventControllerMotion.new()
        ev.connect("enter", lambda x, y, data: self.control_box.set_visible(True))
        ev.connect("leave", lambda data: self.control_box.set_visible(False))
        self.add_controller(ev)
    
    def copy_button_clicked(self, widget):
        display = Gdk.Display.get_default()
        if display is None:
            return
        clipboard = display.get_clipboard()
        clipboard.set_content(Gdk.ContentProvider.new_for_value(self.latex))
        self.copy_button.set_icon_name("object-select-symbolic")


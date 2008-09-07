import os

import gobject
import gtk
import pango

from application import application
from editor import Editor
from format_escaped import format_escaped
from shell_buffer import ShellBuffer
from shell_view import ShellView

class WorksheetEditor(Editor):
    DISCARD_FORMAT = 'Discard unsaved changes to worksheet "%s"?'
    DISCARD_FORMAT_BEFORE_QUIT = 'Save the changes to worksheet "%s" before quitting?'

    def __init__(self, notebook):
        Editor.__init__(self, notebook)

        self.buf = ShellBuffer(self.notebook)
        self.view = ShellView(self.buf)
        self.view.modify_font(pango.FontDescription("monospace"))

        self.widget = gtk.ScrolledWindow()
        self.widget.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.widget.add(self.view)

        self.widget.show_all()

        self.buf.worksheet.connect('notify::filename', lambda *args: self._update_title())
        self.buf.worksheet.connect('notify::code-modified', lambda *args: self._update_title())

    #######################################################
    # Overrides
    #######################################################

    def _get_display_name(self):
        if self.buf.worksheet.filename == None:
            return "Unsaved Worksheet %d" % self._unsaved_index
        else:
            return os.path.basename(self.buf.worksheet.filename)

    def _get_filename(self):
        return self.buf.worksheet.filename

    def _get_modified(self):
        return self.buf.worksheet.code_modified

    def _get_extension(self):
        return "rws"

    def _save(self, filename):
        self.buf.worksheet.save(filename)

    #######################################################
    # Public API
    #######################################################

    def close(self):
        Editor.close(self)
        self.buf.worksheet.close()

    def load(self, filename):
        if not os.path.exists(filename):
            self.buf.worksheet.filename = filename
        else:
            self.buf.worksheet.load(filename)
            self.buf.place_cursor(self.buf.get_start_iter())
            self.view.calculate()
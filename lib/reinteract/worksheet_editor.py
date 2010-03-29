# Copyright 2008-2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import os

import gtk
import pango

from application import application
from editor import Editor
from global_settings import global_settings
from shell_buffer import ShellBuffer
from shell_view import ShellView
import reunicode

class WorksheetEditor(Editor):
    DISCARD_FORMAT = 'Discard unsaved changes to worksheet "%s"?'
    DISCARD_FORMAT_BEFORE_QUIT = 'Save the changes to worksheet "%s" before quitting?'

    def __init__(self, notebook):
        Editor.__init__(self, notebook)

        self.buf = ShellBuffer(self.notebook)
        self.view = ShellView(self.buf)

        self.__font_is_custom_connection = global_settings.connect('notify::editor-font-is-custom', self.__update_font)
        self.__font_name_connection = global_settings.connect('notify::editor-font-name', self.__update_font)
        self.__update_font()

        self.widget = gtk.ScrolledWindow()
        self.widget.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.widget.add(self.view)

        self.widget.show_all()

        self.buf.worksheet.connect('notify::filename', lambda *args: self._update_filename())
        self.buf.worksheet.connect('notify::file', lambda *args: self._update_file())
        self.buf.worksheet.connect('notify::code-modified', lambda *args: self._update_modified())
        self.buf.worksheet.connect('notify::state', lambda *args: self._update_state())

    #######################################################
    # Callbacks
    #######################################################

    def __update_font(self, *arg):
        font_name = "monospace"
        if global_settings.editor_font_is_custom:
            font_name = global_settings.editor_font_name

        self.view.modify_font(pango.FontDescription(font_name))

    #######################################################
    # Overrides
    #######################################################

    def _get_display_name(self):
        if self.buf.worksheet.filename is None:
            return "Unsaved Worksheet %d" % self._unsaved_index
        else:
            return os.path.basename(self.buf.worksheet.filename)

    def _get_filename(self):
        return self.buf.worksheet.filename

    def _get_file(self):
        return self.buf.worksheet.file

    def _get_modified(self):
        return self.buf.worksheet.code_modified

    def _get_state(self):
        return self.buf.worksheet.state

    def _get_extension(self):
        return "rws"

    def _save(self, filename):
        self.buf.worksheet.save(filename)

    @classmethod
    def _validate_name(cls, name):
        return reunicode.validate_name(name)

    #######################################################
    # Public API
    #######################################################

    def close(self):
        Editor.close(self)
        self.buf.worksheet.close()
        global_settings.disconnect(self.__font_is_custom_connection)
        global_settings.disconnect(self.__font_name_connection)

    def load(self, filename, escape=False):
        self.buf.worksheet.load(filename, escape=escape)
        self.buf.place_cursor(self.buf.get_start_iter())

    def calculate(self):
        self.view.calculate()

    def undo(self):
        self.buf.worksheet.undo()

    def redo(self):
        self.buf.worksheet.redo()

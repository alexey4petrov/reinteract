# Copyright 2008-2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import os
import re

import gtk
import pango

from application import application
from editor import Editor
from global_settings import global_settings
from shell_buffer import ShellBuffer
from shell_view import ShellView
from worksheet_print import WorksheetPrintOperation, export_to_pdf

_LETTER_OR_UNDERSCORE = re.compile("[A-Za-z_]")
_LETTER_DIGIT_OR_UNDERSCORE = re.compile("[A-Za-z0-9_]")

class LibraryEditor(Editor):
    DISCARD_FORMAT = 'Discard unsaved changes to library "%s"?'
    DISCARD_FORMAT_BEFORE_QUIT = 'Save the changes to library "%s" before quitting?'

    def __init__(self, notebook):
        Editor.__init__(self, notebook)

        self.buf = ShellBuffer(self.notebook, edit_only=True)
        self.view = ShellView(self.buf)

        self.__font_is_custom_connection = global_settings.watch('editor-font-is-custom', self.__update_font)
        self.__font_name_connection = global_settings.watch('editor-font-name', self.__update_font)
        self.__update_font()

        self.widget = gtk.ScrolledWindow()
        self.widget.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.widget.add(self.view)

        self.widget.show_all()

        self.buf.worksheet.sig_filename_changed.connect( lambda *args: self._update_filename() )
        self.buf.worksheet.sig_file.connect(lambda *args: self._update_file())
        self.buf.worksheet.sig_code_modified.connect(lambda *args: self._update_modified())

    def do_destroy(self):
        self.buf.destroy()
        Editor.do_destroy(self)

    #######################################################
    # Callbacks
    #######################################################

    def __update_font(self):
        font_name = "monospace"
        if global_settings.editor_font_is_custom:
            font_name = global_settings.editor_font_name

        self.view.modify_font(pango.FontDescription(font_name))

    #######################################################
    # Overrides
    #######################################################

    def _get_display_name(self):
        if self.buf.worksheet.filename is None:
            return "Unsaved Library %d" % self._unsaved_index
        else:
            return os.path.basename(self.buf.worksheet.filename)

    def _get_filename(self):
        return self.buf.worksheet.filename

    def _get_file(self):
        return self.buf.worksheet.file

    def _get_modified(self):
        return self.buf.worksheet.code_modified

    def _get_extension(self):
        return "py"

    def _save(self, filename):
        self.buf.worksheet.save(filename)
        self.notebook.reset_module_by_filename(filename)

    def _create_print_operation(self):
        return WorksheetPrintOperation(self.buf.worksheet)

    def _export_to_pdf(self, filename, page_setup):
        export_to_pdf(self.buf.worksheet, filename, page_setup)

    @classmethod
    def _validate_name(cls, name):
        # Remove surrounding whitespace
        name = name.strip()
        if name == "":
            raise ValueError("Name cannot be empty")

        # Remove .py extension if present.
        name = re.sub(r".py$", "", name)

        # Apply identifier rules from
        # http://docs.python.org/reference/lexical_analysis.html
        if not _LETTER_OR_UNDERSCORE.match(name[0]):
            raise ValueError("Library name must start with a Latin letter or "
                             "an underscore")

        for c in name[1:]:
            if not _LETTER_DIGIT_OR_UNDERSCORE.match(c):
                raise ValueError("Library names can only contain Latin "
                                 "letters, numbers and underscores")

        return name

    #######################################################
    # Public API
    #######################################################

    def load(self, filename, escape=False):
        self.buf.worksheet.load(filename, escape=escape)
        self.buf.place_cursor(self.buf.get_start_iter())

    def undo(self):
        self.buf.worksheet.undo()

    def redo(self):
        self.buf.worksheet.redo()

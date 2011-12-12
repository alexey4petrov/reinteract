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
from view_sidebar_layout import ViewSidebarLayout
from worksheet_print import WorksheetPrintOperation, export_to_pdf

class WorksheetEditor(Editor):
    DISCARD_FORMAT = 'Discard unsaved changes to worksheet "%s"?'
    DISCARD_FORMAT_BEFORE_QUIT = 'Save the changes to worksheet "%s" before quitting?'

    def __init__(self, notebook):
        Editor.__init__(self, notebook)

        self.buf = ShellBuffer(self.notebook)
        self.view = ShellView(self.buf)
        self.config_state = None

        self.view.connect('notify::sidebar-open', self.on_notify_sidebar_open)

        global_settings.watch('editor-font-is-custom', self.__update_font)
        global_settings.watch('editor-font-name', self.__update_font)
        self.__update_font()

        self.widget = ViewSidebarLayout()
        self.widget.set_view(self.view)
        self.widget.set_sidebar(self.view.sidebar)
        self.widget.set_sidebar_open(self.view.sidebar_open)
        self.widget.connect('notify::sidebar-width', self.on_notify_sidebar_width)

        self.widget.show_all()

        self.buf.worksheet.sig_filename_changed.connect( lambda *args: self._update_filename() )
        self.buf.worksheet.sig_file.connect( lambda *args: self._update_file() )
        self.buf.worksheet.sig_code_modified.connect( lambda *args: self._update_modified() )
        self.buf.worksheet.sig_state.connect( lambda *args: self._update_state() )

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

    def on_notify_sidebar_open(self, *args):
        self.widget.set_sidebar_open(self.view.sidebar_open)

    def on_notify_sidebar_width(self, *args):
        if self.config_state is not None:
            self.config_state.set_sidebar_width(self.widget.sidebar_width)

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
        old_config_state = self.config_state
        self.buf.worksheet.save(filename)
        self.config_state = application.state.get_worksheet_state(filename)
        if old_config_state:
            old_sidebar_width = old_config_state.get_sidebar_width()
            if old_sidebar_width >= 0:
                self.config_state.set_sidebar_width(old_sidebar_width)

    def _create_print_operation(self):
        return WorksheetPrintOperation(self.buf.worksheet)

    def _export_to_pdf(self, filename, page_setup):
        export_to_pdf(self.buf.worksheet, filename, page_setup)

    @classmethod
    def _validate_name(cls, name):
        return reunicode.validate_name(name)

    #######################################################
    # Public API
    #######################################################

    def load(self, filename, escape=False):
        self.buf.worksheet.load(filename, escape=escape)
        self.buf.place_cursor(self.buf.get_start_iter())
        self.config_state = application.state.get_worksheet_state(filename)
        sidebar_width = self.config_state.get_sidebar_width()
        if sidebar_width >= 0:
            self.widget.sidebar_width = sidebar_width

    def calculate(self, end_at_insert=False):
        self.view.calculate(end_at_insert)

    def interrupt(self):
        self.buf.worksheet.interrupt()

    def undo(self):
        self.buf.worksheet.undo()

    def redo(self):
        self.buf.worksheet.redo()

# Copyright 2008-2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import os
import re
import time

_brackets_re = re.compile(r'([\]\[])')

from notebook_info import format_duration
from config_file import ConfigFile

def _hex_escape(s, unsafe_re):
    return unsafe_re.sub(lambda x: '%%%02x' % ord(x.group(1)), s)

def _section_name(path):
    return _hex_escape(path, _brackets_re)

class NotebookState:
    def __init__(self, app_state, path):
        self.path = path
        self.app_state = app_state
        self.section_name = _section_name(path.encode("UTF-8"))

    def get_open_files(self):
        files = self.app_state.get_list(self.section_name, 'open_files', [])
        return [f.decode("UTF-8") for f in files]

    def get_last_opened(self):
        return self.app_state.get_float(self.section_name, 'last_opened', -1)

    def get_last_opened_text(self):
        return format_duration(self.get_last_opened())

    def get_current_file(self):
        value = self.app_state.get_string(self.section_name, 'current_file')
        if value is not None:
            return value.decode("UTF-8")
        else:
            return None

    def get_size(self):
        width = self.app_state.get_int(self.section_name, 'width', -1)
        height = self.app_state.get_int(self.section_name, 'height', -1)

        return (width, height)

    def get_pane_position(self):
        return self.app_state.get_int(self.section_name, 'pane_position', -1)

    def set_open_files(self, files):
        if not all((isinstance(o, unicode) for o in files)):
            raise ValueError("files argument must contain unicode strings")
        import sys
        self.app_state.set_list(self.section_name, 'open_files',
                                [f.encode("UTF-8") for f in files])

    def set_current_file(self, file):
        if file:
            if not isinstance(file, unicode):
                raise ValueError("files argument must be unicode")
            self.app_state.set_string(self.section_name, 'current_file', file.encode("UTF-8"))
        else:
            self.app_state.remove_option(self.section_name, 'current_file')

    def set_size(self, width, height):
        self.app_state.set_int(self.section_name, 'width', width)
        self.app_state.set_int(self.section_name, 'height', height)

    def set_pane_position(self, position):
        self.app_state.set_int(self.section_name, 'pane_position', position)

    def update_last_opened(self):
        self.app_state.set_float(self.section_name, 'last_opened', time.time())

    def get_pdf_folder(self):
        value = self.app_state.get_string(self.section_name, 'pdf_folder')
        if value is not None:
            return value.decode("UTF-8")
        else:
            return None

    def set_pdf_folder(self, folder):
        if folder:
            if not isinstance(folder, unicode):
                raise ValueError("folder argument must be unicode")

            self.app_state.set_string(self.section_name, 'pdf_folder', folder)
        else:
            self.app_state.remove_option(self._section_name, 'pdf_folder')

class WorksheetState:
    def __init__(self, app_state, path):
        self.path = path
        self.app_state = app_state
        self.section_name = _section_name(path.encode("UTF-8"))

    def get_sidebar_width(self):
        return self.app_state.get_int(self.section_name, 'sidebar_width', -1)

    def set_sidebar_width(self, sidebar_width):
        self.app_state.set_int(self.section_name, 'sidebar_width', sidebar_width)

class ApplicationState(ConfigFile):
    def __init__(self, location):
        ConfigFile.__init__(self, location)
        self.notebook_states = {}
        self.worksheet_states = {}

    def __get_recent_notebook_paths(self):
        return self.get_list('Reinteract', 'recent_notebooks', [])

    def notebook_opened(self, path):
        nb_state = self.get_notebook_state(path)
        nb_state.update_last_opened()

        old_paths = self.__get_recent_notebook_paths()
        try:
            old_paths.remove(path)
        except ValueError:
            pass
        old_paths.insert(0, path)

        self.set_list('Reinteract', 'recent_notebooks', old_paths)

    def get_recent_notebooks(self, max_count=10):
        paths = self.__get_recent_notebook_paths()
        if max_count >= 0:
            paths = paths[0:max_count]

        return [self.get_notebook_state(path.decode("UTF-8")) for path in paths]

    def get_notebook_state(self, path):
        if not path in self.notebook_states:
            self.notebook_states[path] = NotebookState(self, path)

        return self.notebook_states[path]

    def get_worksheet_state(self, path):
        if not path in self.worksheet_states:
            self.worksheet_states[path] = WorksheetState(self, path)

        return self.worksheet_states[path]

######################################################################

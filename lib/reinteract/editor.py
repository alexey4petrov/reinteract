# Copyright 2008-2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import os

import glib
import gobject
import gtk
import pango

from application import application
from destroyable import Destroyable
from format_escaped import format_escaped
from notebook import NotebookFile
from shell_buffer import ShellBuffer
from shell_view import ShellView
from save_file import SaveFileBuilder

class Editor(Destroyable, gobject.GObject):
    __gsignals__ = {
        'filename-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
    }

    def __init__(self, notebook):
        gobject.GObject.__init__(self)

        self.notebook = notebook
        self._unsaved_index = application.allocate_unsaved_index()
        self.__pdf_filename = None

    def do_destroy(self):
        if self._unsaved_index is not None:
            application.free_unsaved_index(self._unsaved_index)
            self._unsaved_index = None

        self.widget.destroy()

        Destroyable.do_destroy(self)

    #######################################################
    # Utility
    #######################################################

    def _clear_unsaved(self):
        if self._unsaved_index is not None:
            application.free_unsaved_index(self._unsaved_index)
            self._unsaved_index = None

    def _update_filename(self, *args):
        self.emit('filename-changed')
        self.notify('title')

    def _update_modified(self, *args):
        self.notify('modified')
        self.notify('title')

    def _update_state(self, *args):
        self.notify('state')

    def _update_file(self):
        self.notify('file')

    def __prompt_for_name(self, title, save_button_text, action, check_name=None):
        builder = SaveFileBuilder(title, self._get_display_name(), save_button_text, self._validate_name, check_name)
        builder.dialog.set_transient_for(self.widget.get_toplevel())

        if self._get_filename() is not None:
            builder.name_entry.set_text(os.path.basename(self._get_filename()))

        builder.prompt_for_name(self.notebook.folder, self._get_extension(), action)

        builder.dialog.destroy()

    def _get_page_setup(self):
        return application.get_page_setup()

    def _save_page_setup(self, page_setup):
        application.save_page_setup(page_setup)

    def _get_print_settings(self):
        return application.get_print_settings()

    def _save_print_settings(self, print_settings):
        application.save_print_settings(print_settings)

    #######################################################
    # Implemented by subclasses
    #######################################################

    def _get_display_name(self):
        raise NotImplementedError()

    def _get_modified(self):
        raise NotImplementedError()

    def _get_state(self):
        return NotebookFile.NONE

    def _get_filename(self):
        return NotImplementedError()

    def _get_file(self):
        return NotImplementedError()

    def _get_extension(self):
        return NotImplementedError()

    def _save(self, filename):
        return NotImplementedError()

    def _export_to_pdf(self, filename, page_setup):
        return NotImplementedError()

    @classmethod
    def _validate_name(cls, name):
        return NotImplementedError()

    #######################################################
    # Public API
    #######################################################

    def confirm_discard(self, before_quit=False):
        if not self.modified:
            return True

        if before_quit:
            message_format = self.DISCARD_FORMAT_BEFORE_QUIT
            continue_button_text = '_Quit without saving'
        else:
            message_format = self.DISCARD_FORMAT
            continue_button_text = '_Discard'

        if self._get_filename() is None:
            save_button_text = gtk.STOCK_SAVE_AS
        else:
            save_button_text = gtk.STOCK_SAVE

        message = format_escaped("<big><b>" + message_format + "</b></big>", self._get_display_name())

        dialog = gtk.MessageDialog(parent=self.widget.get_toplevel(), buttons=gtk.BUTTONS_NONE,
                                   type=gtk.MESSAGE_WARNING)
        dialog.set_markup(message)

        dialog.add_buttons(continue_button_text, gtk.RESPONSE_OK,
                           gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                           save_button_text, 1)
        dialog.set_default_response(1)
        response = dialog.run()
        dialog.destroy()

        if response == gtk.RESPONSE_OK:
            return True
        elif response == 1:
            self.save()

            if self.modified:
                return False
            else:
                return True
        else:
            return False

    def wait_for_execution(self):
        if self.state != NotebookFile.EXECUTING:
            return True

        message = format_escaped('<b>Waiting for "%s" to finish executing...</b>"', self._get_display_name());

        dialog = gtk.MessageDialog(parent=self.widget.get_toplevel(), buttons=gtk.BUTTONS_NONE,
                                   type=gtk.MESSAGE_INFO)
        dialog.set_markup(message)

        dialog.add_buttons("_Interrupt", 1,
                           gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dialog.set_default_response(gtk.RESPONSE_CANCEL)

        loop = glib.MainLoop()

        def on_response(dialog, response):
            if response == 1:
                self.interrupt()
            else:
                loop.quit()
        dialog.connect("response", on_response)

        def on_state_changed(self, paramspec):
            if self.state != NotebookFile.EXECUTING:
                loop.quit()
        state_changed_id = self.connect("notify::state", on_state_changed)

        dialog.set_modal(True)
        dialog.show()
        loop.run()
        dialog.destroy()

        self.disconnect(state_changed_id)

        return self.state != NotebookFile.EXECUTING

    def load(self, filename, escape=False):
        """Load a file from disk into the editor. Can raise IOError if the
        file cannot be read, and reunicode.ConversionError if the file contains
        invalid characters. (reunicode.ConversionError will not be raised if
        escape is True)

        @param filename the file to load
        @param escape if true, invalid byte and character sequences in the input
           will be converted into \\x<nn> and \\u<nnnn> escape sequences.

        """
        raise NotImplementedError()

    def save(self, filename=None):
        if filename is None:
            filename = self._get_filename()

        if filename is None:
            def action(fullname):
                self._save(fullname)
                self._clear_unsaved()
                self.notebook.refresh()

            self.__prompt_for_name(title="Save As...", save_button_text="_Save", action=action)
        else:
            self._save(filename)

    def rename(self):
        if self._get_filename() is None:
            self.save()
            return

        old_name = os.path.basename(self._get_filename())

        title = "Rename '%s'" % old_name

        def check_name(name):
            return name != "" and name != old_name

        def action(fullname):
            old_filename = self._get_filename()
            self._save(fullname)
            self._clear_unsaved()
            os.remove(old_filename)
            self.notebook.refresh()
            self.__pdf_filename = None

        self.__prompt_for_name(title=title, save_button_text="_Rename", action=action, check_name=check_name)

    @classmethod
    def validate_name(cls, name):
        return cls._validate_name(name)

    @property
    def needs_calculate(self):
        return (self.state != NotebookFile.EXECUTE_SUCCESS and
                self.state != NotebookFile.NONE and
                self.state != NotebookFile.EXECUTING)

    def calculate(self, end_at_insert=False):
        pass

    def interrupt(self):
        pass

    def page_setup(self):
        page_setup = gtk.print_run_page_setup_dialog(self.widget.get_toplevel(),
                                                     self._get_page_setup(),
                                                     self._get_print_settings())
        self._save_page_setup(page_setup)

    def print_contents(self):
        print_op = self._create_print_operation()
        print_op.set_embed_page_setup(True)

        print_op.set_default_page_setup(self._get_page_setup())
        print_op.set_print_settings(self._get_print_settings())

        if print_op.run(gtk.PRINT_OPERATION_ACTION_PRINT_DIALOG, self.widget.get_toplevel()):
            self._save_page_setup(print_op.get_default_page_setup())
            self._save_print_settings(print_op.get_print_settings())

    def export_to_pdf(self):
        ### Get the filename to save to ###

        chooser = gtk.FileChooserDialog("Export to PDF...",
                                        self.widget.get_toplevel(),
                                        gtk.FILE_CHOOSER_ACTION_SAVE,
                                        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                         gtk.STOCK_SAVE,   gtk.RESPONSE_OK))
        chooser.set_default_response(gtk.RESPONSE_OK)

        # We reuse the last filename that the use exported to in this
        # run of the application, otherwise we base the exported name
        # on the worksheet name

        if self.__pdf_filename is None:
            basename = os.path.basename(self.filename)
            if basename.endswith(".rws") or basename.endswith(".RWS"):
                basename = basename[:-4]
            elif  basename.endswith(".py") or basename.endswith(".PY"):
                basename = basename[:-3]

            self.__pdf_filename = basename + ".pdf"

        chooser.set_current_name(self.__pdf_filename)

        # The export folder is saved persistantly (relative to the notebook
        # folder if it's inside it)

        notebook_state = application.state.get_notebook_state(self.notebook.folder)
        folder = notebook_state.get_pdf_folder()

        if folder is None:
            folder = self.notebook.folder
        elif not os.path.isabs(folder):
            folder = os.path.join(self.notebook.folder, folder)

        chooser.set_current_folder(folder)

        while True:
            response = chooser.run()
            filename = None
            if response != gtk.RESPONSE_OK:
                chooser.destroy()
                return

            # Overwrite confirmation

            filename = chooser.get_filename()
            if os.path.exists(filename):
                dialog = gtk.MessageDialog(parent=chooser, buttons=gtk.BUTTONS_NONE,
                                           type=gtk.MESSAGE_QUESTION)
                dialog.set_markup(format_escaped("<big><b>Replace '%s'?</b></big>", os.path.basename(filename)))
                dialog.format_secondary_text("The file already exists in \"%s\".  Replacing it will "
                                             "overwrite its contents." % os.path.dirname(filename))

                dialog.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                   "_Replace", gtk.RESPONSE_OK)
                dialog.set_default_response(gtk.RESPONSE_OK)

                response = dialog.run()
                dialog.destroy()
                if response == gtk.RESPONSE_OK:
                    break
            else:
                break

        filename = filename.decode('UTF-8')

        ### Save the PDF ###

        self._export_to_pdf(filename, self._get_page_setup())

        ### Now save the selected folder and filename later use ###

        folder = os.path.dirname(filename)

        parent = folder
        while True:
            if parent == self.notebook.folder:
                folder = os.path.relpath(folder, self.notebook.folder)
                break

            tmp = os.path.dirname(parent)
            if tmp == parent:
                break
            parent = tmp

        if not isinstance(folder, unicode):
            folder = folder.decode("UTF-8")

        notebook_state.set_pdf_folder(folder)
        self.__pdf_filename = os.path.basename(filename)

        chooser.destroy()

    def undo(self):
        pass

    def redo(self):
        pass

    # This should be a gobject.property, but we define filenames to be unicode strings
    # and it's impossible to have a unicode-string valued property. Unicode strings
    # set on a string gobject.property get endecoded to UTF-8. So, we use the separate
    # ::filename-changed signal.
    @property
    def filename(self):
        return self._get_filename()

    @gobject.property
    def file(self):
        return self._get_file()

    @gobject.property
    def modified(self):
        return self._get_modified()

    @gobject.property
    def state(self):
        return self._get_state()

    @gobject.property
    def title(self):
        if self.modified:
            return "*" + self._get_display_name()
        else:
            return self._get_display_name()

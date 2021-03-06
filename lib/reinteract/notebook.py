# Copyright 2007-2009 Owen Taylor
# Copyright 2008 Jon Kuhn
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import copy
import gio
import gobject
import imp
import os
import pkgutil
import sys

from notebook_info import NotebookInfo
import reunicode

# Used to give each notebook a unique namespace
_counter = 1

# Hook the import function in the global __builtin__ module; this is used to make
# imports from a notebook locally scoped to that notebook. We do it this way
# rather than replacing __builtins__ to avoid triggering restricted mode.
import __builtin__
saved_import = __builtin__.__import__
def reinteract_import(name, globals=None, locals=None, fromlist=None, level=-1):
    if globals and '__reinteract_notebook' in globals:
        return globals['__reinteract_notebook'].do_import(name, globals, locals, fromlist, level)
    else:
        return saved_import(name, globals, locals, fromlist, level)

__builtin__.__import__ = reinteract_import

class HelpResult:
    def __init__(self, arg):
        self.arg = arg

class _Helper:
    # We use a callable object here rather than a function so that we handle
    # help without arguments, just like the help builtin
    def __repr__(self):
        return "Type help(object) for help about object"

    def __call__(self, arg=None):
        if arg is None:
            return self
        
        return HelpResult(arg)

class _Builder:
    def __init__(self, arg=None):
        self.arg = arg

    def __enter__(self):
        if hasattr(self.arg, '__enter__'):
            return self.arg.__enter__()
        else:
            return self.arg

    def __exit__(self, exception_type, exception_value, traceback):
        if hasattr(self.arg, '__exit__'):
            return self.arg.__exit__(exception_type, exception_value, traceback)

######################################################################

class NotebookFile(gobject.GObject):
    NONE = 0
    NEEDS_EXECUTE = 1
    EXECUTING = 2
    EXECUTE_SUCCESS = 3
    ERROR = 4

    active = gobject.property(type=bool, default=False)
    modified = gobject.property(type=bool, default=False)
    state = gobject.property(type=int, default=NONE)
    worksheet = gobject.property(type=gobject.TYPE_PYOBJECT)

    # Having this here in the core code is completely random, however it doesn't actually
    # require importing GTK+, it's just returning a string.
    @staticmethod
    def stock_id_for_state(state):
        """Get the GTK+ stock ID to use for a particular state."""

        if state == NotebookFile.NONE:
            return None
        elif state == NotebookFile.NEEDS_EXECUTE:
            return 'gtk-ok'
        elif state == NotebookFile.EXECUTING:
            return 'gtk-refresh'
        elif state == NotebookFile.EXECUTE_SUCCESS:
            return 'gtk-apply'
        elif state == NotebookFile.ERROR:
            return 'gtk-dialog-error'

    def __init__(self, path):
        if not isinstance(path, unicode):
            raise ValueError("path argument must be unicode")

        gobject.GObject.__init__(self)
        self.path = path

class WorksheetFile(NotebookFile):
    pass

class LibraryFile(NotebookFile):
    pass

class MiscFile(NotebookFile):
    pass

######################################################################

class Notebook(gobject.GObject):
    __gsignals__ = {
        'files-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
    }

    def __init__(self, folder=None):
        if folder is not None and not isinstance(folder, unicode):
            raise ValueError("folder argument must be unicode")

        gobject.GObject.__init__(self)

        global _counter

        self.__prefix = "__reinteract" + str(_counter)
        _counter += 1


        self.folder = folder

        if folder:
            path = [folder]
        else:
            path = []

        self.__path = path
        self.__modules = {}

        self.__root_module = imp.new_module(self.__prefix)
        self.__root_module.path = path
        sys.modules[self.__prefix] = self.__root_module

        self.files = {}
        self.__monitors = {}
        self.worksheets = set()


        if folder:
            self.info = NotebookInfo(folder)
        else:
            self.info = None

        self.refresh()

    ############################################################
    # Loading and Saving
    ############################################################

    def __load_files(self, folder, old_files, new_files, old_monitors, new_monitors):
        if folder:
            full_folder = os.path.join(self.folder, folder)
        else:
            full_folder = self.folder

        if full_folder in old_monitors:
            new_monitors[full_folder] = old_monitors[full_folder]
            del old_monitors[full_folder]
        else:
            try:
                new_monitors[full_folder] = gio.File(full_folder).monitor_directory()
                new_monitors[full_folder].connect("changed", self._on_monitor_changed)
            except gio.Error:
                pass # probably not supported on the operating system

        files_added = False

        for f in os.listdir(full_folder):
            f = reunicode.canonicalize_filename(f)

            if folder is None and f == "index.rnb":
                continue

            # We handle filenames starting with . as hidden on all platforms,
            # valuing notebook portability over exact correspondance with
            # local convention.
            if f.startswith('.'):
                continue

            if folder:
                relative = os.path.join(folder, f)
            else:
                relative = f

            full_path = os.path.join(full_folder, f)

            if os.path.isdir(full_path):
                files_added = self.__load_files(relative, old_files, new_files, old_monitors, new_monitors) or files_added
            elif relative in old_files:
                new_files[relative] = old_files[relative]
                del old_files[relative]
            elif f.endswith('~'):
                pass
            else:
                lower = f.lower()
                if lower.endswith('.rws'):
                    file = WorksheetFile(relative)
                    absolute = os.path.join(full_folder, f)
                    for worksheet in self.worksheets:
                        if worksheet.filename and os.path.abspath(worksheet.filename) == absolute:
                            file.worksheet = worksheet
                            break
                elif lower.endswith('.py'):
                    file = LibraryFile(relative)
                elif lower.endswith('.pyc') or lower.endswith('.pyo'):
                    continue
                else:
                    file = MiscFile(relative)
                new_files[relative] = file
                files_added = True

        return files_added

    def _on_monitor_changed(self, monitor, f, other_file, event_type):
        if event_type in (gio.FILE_MONITOR_EVENT_CREATED,
                          gio.FILE_MONITOR_EVENT_DELETED,
                          gio.FILE_MONITOR_EVENT_MOVED):
            self.refresh()

    ############################################################
    # Import handling
    ############################################################

    def __reset_all_modules(self):
        for (name, module) in self.__modules.iteritems():
            del sys.modules[self.__prefix + "." + name]
            for worksheet in self.worksheets:
                worksheet.module_changed(name)

        self.__modules = {}

    def reset_module_by_filename(self, filename):
        filename = filename.lower()
        for (name, module) in self.__modules.iteritems():
            # If the .py changed, we need to reload the module even if it was
            # loaded from a .pyc file.
            module_file = module.__file__.lower()
            if module_file.endswith(".pyc") or module_file.endswith(".pyo"):
                module_file = module_file[:-3] + "py"

            if module_file == filename:
                del sys.modules[self.__prefix + "." + name]
                del self.__modules[name]

                for worksheet in self.worksheets:
                    worksheet.module_changed(name)

                return module

    def __load_local_module(self, fullname, loader):
        prefixed = self.__prefix + "." + fullname
        
        # Trick ... to change the builtins array for the module we are about
        # to load, we stick an empty module initialized the way we want into
        # sys.modules and count on imp.load_module() finding that and doing
        # the rest of the loading into that module

        new = imp.new_module(prefixed)
        self.setup_globals(new.__dict__)
        new.__name__ = fullname
        
        assert not prefixed in sys.modules
        sys.modules[prefixed] = new
        self.__modules[fullname] = new
        try:
            result = loader.load_module(prefixed)
        except SyntaxError, e:
            del sys.modules[prefixed]
            del self.__modules[fullname]
            raise
        except:
            # For runtime errors, Python will do the cleanup of sys.modules
            del self.__modules[fullname]
            raise
        assert result == new

        return result

    # Unlike imp.find_module(), pkgutil.find_loader() doesn't take a path
    # argument, so when we want to look in a specific path we need to "roll
    # our own" out of lower level functionality.
    def __find_loader_in_path(self, fullname, path):
        for item in path:
            importer = pkgutil.get_importer(item)
            loader = importer.find_module(fullname)
            if loader is not None:
                return loader

        raise ImportError("no module named " + fullname)

    def __find_and_load(self, fullname, name, parent=None, local=None):
        # The 'imp' module doesn't support PEP 302 extensions like
        # sys.path_hooks (used for zipped eggs), so we use (undocumented)
        # functionality from pkgutil instead.
        if parent is None:
            assert local is None
            try:
                loader = self.__find_loader_in_path(fullname, self.__path)
                local = True
            except ImportError:
                loader = pkgutil.find_loader(fullname)
                if loader is None:
                    raise ImportError("no module named " + fullname)
                local = False
        else:
            assert local is not None
            if hasattr(parent, '__path__'):
                loader = self.__find_loader_in_path(fullname, parent.__path__)
            else:
                raise ImportError("no module named " + fullname)

        if local:
            module = self.__load_local_module(fullname, loader)
        else:
            module =  loader.load_module(fullname)

        if parent is not None:
            parent.__dict__[name] = module

        return module, local
        
    def __import_recurse(self, names):
        fullname = ".".join(names)
        
        try:
            return self.__modules[fullname], True
        except KeyError:
            pass
        
        try:
            return sys.modules[fullname], False
        except KeyError:
            pass

        if len(names) == 1:
            module, local = self.__find_and_load(fullname, names[-1])
        else:
            parent, local = self.__import_recurse(names[0:-1])

            # Loading the parent might have loaded the module we were looking for
            try:
                return self.__modules[fullname], True
            except KeyError:
                pass

            module, _ = self.__find_and_load(fullname, names[-1], parent=parent, local=local)

        return module, local

    def __ensure_from_list_item(self, fullname, fromname, module, local):
        if fromname == "*": # * inside __all__, ignore
            return
        
        if not isinstance(fromname, basestring):
            raise TypeError("Item in from list is not a string")
        
        try:
            getattr(module, fromname)
        except AttributeError:
            try:
                self.__find_and_load(fullname + "." + fromname, fromname, parent=module, local=local)
            except ImportError:
                pass

    def __get_package(self, globals):
        # The behavior of core Python is to set module.__package__ to None when
        # the module is created, then to compute and cache __package__ the first
        # time it is needed for an import within the module. A bit silly, since
        # that means negative results aren't cached, but we follow along.

        if '__package__' in globals and globals['__package__'] is not None:
            return globals['__package__'] # previously cached

        if globals is None or not '__name__' in globals:
            return None # not in a package

        name = globals['__name__']

        if '__path__' in globals:
            # If __path__ is set, then the caller is itself a package
            package = name
        else:
            try:
                dotindex = name.rindex('.')
            except ValueError:
                return None

            package = name[0:dotindex]

        globals['__package__'] = package # cache

        return package

    def __add_wrapper(self, globals_, module):
        if hasattr(module, '__reinteract_wrap__'):
            old = globals_['__reinteract_wrappers']
            globals_['__reinteract_wrappers'] = [getattr(module, '__reinteract_wrap__')]
            globals_['__reinteract_wrappers'].extend(old)

    def do_import(self, name, globals=None, locals=None, fromlist=None, level=None):
        # Holding the import lock around the whole import process matches what
        # Python does internally. This does mean that the machinery of loading a slow
        # import blocks the import of an already loaded module in a different thread.
        # You could imagine trying to do the lookup without the lock and locking only
        # for loading, but ensuring the safety of that would be quite complex
        imp.acquire_lock()
        try:
            names = name.split('.')

            # we want to return the module pointed to by the first component of name;
            # even if name is a relative name not an absolute name. return_index
            # is the index of name within the absolute name
            return_index = 0

            if level != 0:
                package = self.__get_package(globals)
                if package is not None:
                    package_names = package.split('.')

            if level == -1 and package is not None:
                # Pre-PEP 328, first try local import, then global import
                try:
                    tmp_names = package_names + names
                    module, local = self.__import_recurse(tmp_names)
                    names = tmp_names
                    return_index = len(package_names)
                except ImportError:
                    module, local = self.__import_recurse(names)
            else:
                if level > 0:
                    # Relative import, figure out the absolute name we're importing
                    return_index = level
                    if package is None:
                        raise ValueError("ValueError: Attempted relative import in non-package")
                    elif level - 1 > len(package_names):
                        raise ValueError("Attempted relative import beyond toplevel package")

                    if level > 1:
                        package_names = package_names[0:-(level - 1)]

                    names = package_names + names

                module, local =  self.__import_recurse(names)

            if fromlist is not None:
                # In 'from a.b import c', if a.b.c doesn't exist after loading a.b, The built-in
                # __import__ will try to load a.b.c as a module; do the same here.
                for fromname in fromlist:
                    if fromname == "*":
                        try:
                            all = getattr(module, "__all__")
                            for allname in all:
                                self.__ensure_from_list_item(name, allname, module, local)
                        except AttributeError:
                            pass

                        self.__add_wrapper(globals, module)
                    else:
                        self.__ensure_from_list_item(name, fromname, module, local)

                return module
            else:
                self.__add_wrapper(globals, module)

                return_name = ".".join(names[0:return_index + 1])

                if local:
                    return self.__modules[return_name]
                else:
                    return sys.modules[return_name]
        finally:
            imp.release_lock()

    ############################################################
    # Worksheet tracking
    #############################################################

    def _add_worksheet(self, worksheet):
        # Called from Worksheet
        self.worksheets.add(worksheet)

    def _remove_worksheet(self, worksheet):
        # Called from Worksheet
        self.worksheets.remove(worksheet)

    ############################################################
    # Public API
    ############################################################

    def refresh(self):
        if not self.folder:
            return

        old_files = self.files
        self.files = {}
        old_monitors = self.__monitors
        self.__monitors = {}
        files_added = self.__load_files(None, old_files, self.files, old_monitors, self.__monitors)
        if files_added or len(old_files) > 0:
            self.emit('files-changed')

    def set_path(self, path):
        if path != self.__path:
            self.__path = path
            self.__root_module.path = path
            self.__reset_all_modules()

    def setup_globals(self, globals):
        globals['__reinteract_notebook'] = self
        globals['__reinteract_copy'] = copy.copy
        globals['__reinteract_wrappers'] = []
        globals['__reinteract_builder'] = _Builder
        globals['help'] = _Helper()

    def file_for_absolute_path(self, absolute_path):
        if not isinstance(absolute_path, unicode):
            raise ValueError("absolute_path argument must be unicode")

        assert absolute_path
        assert os.path.isabs(absolute_path)

        if not self.folder:
            return None

        relpath = None
        while absolute_path != self.folder:
            absolute_path, basename = os.path.split(absolute_path)
            if basename == '': # At root directory (or input had trailing slash)
                return None

            if relpath is None:
                relpath = basename
            else:
                relpath = os.path.join(basename, relpath)

        if relpath and relpath in self.files:
            return self.files[relpath]
        else:
            return None

    def save(self):
        pass

    def close(self):
        self.__monitors = None
        self.__reset_all_modules()
    

########################################################################

# Copyright 2007-2009 Owen Taylor
# Copyright 2008 Jon Kuhn
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import copy
import gobject
import imp
import os
import pkgutil
import sys

from notebook_info import NotebookInfo

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
            raise ValueError("Argument to NotebookFile must be unicode")

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
            raise ValueError("Argument to Notebook must be unicode")

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
        self.worksheets = set()

        if folder:
            self.info = NotebookInfo(folder)
        else:
            self.info = None

        self.refresh()

    ############################################################
    # Loading and Saving
    ############################################################

    def __load_files(self, folder, old_files, new_files):
        if folder:
            full_folder = os.path.join(self.folder, folder)
        else:
            full_folder = self.folder

        files_added = False

        for f in os.listdir(full_folder):
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
                files_added = self.__load_files(relative, old_files, new_files) or files_added
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
            self.__find_and_load(fullname + "." + fromname, fromname, parent=module, local=local)

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
                    else:
                        self.__ensure_from_list_item(name, fromname, module, local)

                return module
            else:
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
        files_added = self.__load_files(None, old_files, self.files)
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
        globals['help'] = _Helper()

    def file_for_absolute_path(self, absolute_path):
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
    
if __name__ == '__main__':
    import copy
    import os
    import tempfile
    import zipfile
    
    from test_utils import assert_equals

    base = tempfile.mkdtemp("", u"shell_buffer")
    
    def cleanup():
        for root, dirs, files in os.walk(base, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))

    def cleanup_pyc():
        # Not absolutely necessary, but makes things less confusing if we do
        # this between tests
        for root, dirs, files in os.walk(base, topdown=False):
            for name in files:
                if name.endswith(".pyc"):
                    os.remove(os.path.join(root, name))
                
    def write_file(name, contents):
        absname = os.path.join(base, name)
        dirname = os.path.dirname(absname)
        try:
            os.makedirs(dirname)
        except:
            pass

        f = open(absname, "w")
        f.write(contents)
        f.close()

    def write_zipfile(zippath, name, contents):
        abspath = os.path.join(base, zippath)
        dirpath = os.path.dirname(abspath)
        try:
            os.makedirs(dirpath)
        except:
            pass

        if os.path.exists(abspath):
            zip = zipfile.ZipFile(abspath, "a")
        else:
            zip = zipfile.ZipFile(abspath, "w")
        zip.writestr(name, contents)
        zip.close()

    def do_test(import_text, evaluate_text, expected, nb=None):
        if nb is None:
            nb = Notebook(base)

        scope = {}
        nb.setup_globals(scope)
        
        exec import_text in scope
        result = eval(evaluate_text, scope)

        assert_equals(result, expected)

        cleanup_pyc()

    try:
        write_file("mod1.py", "a = 1")
        write_file("package1/__init__.py", "import os\n__all__ = ['mod2']")
        write_file("package1/mod2.py", "b = 2")
        write_file("package1/mod8.py", "import os\nimport mod2\nf = mod2.b + 1")
        write_file("package1/mod9.py", "from __future__ import absolute_import\nfrom . import mod2\ng = mod2.b + 2")
        write_file("package2/__init__.py", "")
        write_file("package2/mod3.py", "import package1.mod2\nc = package1.mod2.b + 1")

        sys.path.append(os.path.join(base, "ZippedModules.zip"))
        write_zipfile("ZippedModules.zip", "zipmod.py", "d = 4");
        write_zipfile("ZippedModules.zip", "zippackage/__init__.py", "");
        write_zipfile("ZippedModules.zip", "zippackage/mod2.py", "e = 5");

        do_test("import mod1", "mod1.__file__", os.path.join(base, "mod1.py"))

        do_test("import mod1", "mod1.a", 1)
        do_test("import mod1 as m", "m.a", 1)
        do_test("from mod1 import a", "a", 1)
        do_test("from mod1 import a as a2", "a2", 1)

        do_test("import package1.mod2", "package1.mod2.b", 2)
        do_test("import package1.mod2 as m", "m.b", 2)
        do_test("from package1 import mod2", "mod2.b", 2)
        do_test("from package1 import *", "mod2.b", 2)

        do_test("import package1.mod8", "package1.mod8.f", 3);
        do_test("import package1.mod9", "package1.mod9.g", 4);

        # Test loading the same local module a second time in the same notebook
        nb = Notebook(base)
        do_test("import package1.mod2", "package1.mod2.b", 2, nb=nb)
        do_test("import package1.mod2", "package1.mod2.b", 2, nb=nb)

        # http://www.reinteract.org/trac/ticket/5
        do_test("import package2.mod3", "package2.mod3.c", 3)

        do_test("import zipmod", "zipmod.d", 4)
        do_test("import zippackage.mod2", "zippackage.mod2.e", 5)

        # Test changing file contents and reloading the module
        nb = Notebook(base)
        write_file("mod4.py", "a = 1")
        do_test("import mod4", "mod4.a", 1, nb=nb)
        write_file("mod4.py", "a = 2")
        nb.reset_module_by_filename(os.path.join(base, "mod4.py"))
        do_test("import mod4", "mod4.a", 2, nb=nb)

        # Test recovering from a syntax error
        nb = Notebook(base)
        write_file("mod4.py", "= 1")
        try:
            do_test("import mod4", "mod4.a", 1, nb=nb)
        except SyntaxError, e:
            pass
        write_file("mod4.py", "a = 1")
        nb.reset_module_by_filename(os.path.join(base, "mod4.py"))
        do_test("import mod4", "mod4.a", 1, nb=nb)

        # Test recovering from a runtime error during import
        nb = Notebook(base)
        write_file("mod5.py", "a = b")
        try:
            do_test("import mod5", "mod5.a", 1, nb=nb)
        except NameError, e:
            pass
        # the old and new files will have the same second-resolution timestamps
        cleanup_pyc()
        write_file("mod5.py", "a = 1")
        nb.reset_module_by_filename(os.path.join(base, "mod5.py"))
        do_test("import mod5", "mod5.a", 1, nb=nb)

        nb = Notebook(base)
        assert_equals(nb.file_for_absolute_path(os.path.dirname(base)), None)
        assert_equals(nb.file_for_absolute_path(base), None)
        assert_equals(nb.file_for_absolute_path(os.path.join(base, "mod1.py")).path, "mod1.py")
        assert_equals(nb.file_for_absolute_path(os.path.join(base, "package1")), None)
        assert_equals(nb.file_for_absolute_path(os.path.join(base, "package1/")), None)
        assert_equals(nb.file_for_absolute_path(os.path.join(base, "package1/mod2.py")).path, "package1/mod2.py")

        # Simple test of isolation - if this was the same notebook, then
        # we'd need to reset_module_by_filename()
        write_file("mod6.py", "import mod7\na = mod7.a");
        write_file("mod7.py", "a = 1")
        do_test("import mod6", "mod6.a", 1) # creates a new notebook
        cleanup_pyc()
        write_file("mod7.py", "a = 2")
        do_test("import mod6", "mod6.a", 2) # creates a different new notebook

    finally:
        cleanup()

#!/usr/bin/env python

########################################################################
#
# Copyright 2007-2009 Owen Taylor
# Copyright 2008 Jon Kuhn
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

    
#--------------------------------------------------------------------------------------
def test_notebook_0():
    #--------------------------------------------------------------------------------------
    from test_utils import adjust_environment, assert_equals
    adjust_environment()

    from reinteract.notebook import Notebook

    import copy
    import os, sys
    import tempfile
    import zipfile
    
    #--------------------------------------------------------------------------------------
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
        write_file("mod10.py", "def __reinteract_wrap__(obj): return 2")
        write_file("mod11.py", "def __reinteract_wrap__(obj): return 3")

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

        # Simple test of __reinteract_wrap__; last has highest priority
        do_test("import mod10\nimport mod11", "__reinteract_wrappers[0](1)", 3)
        do_test("import mod10\nimport mod11", "__reinteract_wrappers[1](1)", 2)

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

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_notebook_0()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------

# Copyright 2008 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import glob
import logging
import os
import re
import shutil
import tempfile

from am_parser import AMParser
from utils import check_call

_logger = logging.getLogger("Builder")

class Builder(object):
    """
    The Builder class contains code for assembling a tree of files from various
    sources (arbitrary files on the filesystem, Python modules from the Python
    path, files in the Reinteract source tree.) This is then subclassed to build
    that tree of files into an installer.
    """

    def __init__(self, topdir, treesubdir='Reinteract'):
        self.topdir = topdir
        self.file_attributes = {}
        self.main_am = None

        self.tempdir = tempfile.mkdtemp("", "reinteract_build.")
        self.treedir = os.path.join(self.tempdir, treesubdir)

        _logger.debug("Top source directory is %s", topdir)
        _logger.info("Temporary directory is %s", self.tempdir)

    def cleanup(self):
        """Remove temporary files"""

        try:
            shutil.rmtree(self.tempdir)
        except:
            pass

    def add_file(self, source, directory, **attributes):
        """
        Add a file into the temporary tree

        @param source: the file to add. If relative, it is taken to be relative
          to the top of the Reinteract source distribution.
        @param directory: directory to add it in (relative to the top of the temporary tree)
        @param attributes: attributes to store for the file

        """
        absdir = os.path.join(self.treedir, directory)
        if os.path.isabs(source):
            abssource = source
        else:
            abssource = os.path.join(self.topdir, source)
        _logger.debug("Copying %s to %s", abssource, directory)
        if not os.path.isdir(absdir):
            os.makedirs(absdir)
        absdest = os.path.join(absdir, os.path.basename(source))
        shutil.copy(abssource, absdest)

        relative = os.path.normpath(os.path.join(directory, os.path.basename(source)))

        self.file_attributes[relative] = attributes

    def add_files_from_directory(self, sourcedir, directory, exclude=None, **attributes):
        """
        Add a directory of files into the temporary tree

        @param source: the directory to add. If relative, it is taken to be relative
          to the top of the Reinteract source distribution.
        @param directory: directory put files into (relative to the top of the temporary tree)
        @param attributes: attributes passed to add_file() for each file
        @param exclude: if present, a list of regular expression objects to match
          against filenames (using .match() so anchored at the beginning). Filenames
          that match are excluded.

        """

        if os.path.isabs(sourcedir):
            abssourcedir = sourcedir
        else:
            abssourcedir = os.path.join(self.topdir, sourcedir)

        for f in os.listdir(abssourcedir):
            excluded = False
            if exclude is not None:
                for pattern in exclude:
                    if pattern.match(f):
                        excluded = True
            if excluded:
                continue

            absf = os.path.join(abssourcedir, f)
            if os.path.isdir(absf):
                self.add_files_from_directory(absf, os.path.join(directory, f),
                                              exclude=exclude,
                                              **attributes)
            else:
                self.add_file(absf, directory, **attributes)

    def add_matching_files(self, sourcedir, patterns, directory, **attributes):
        """
        Add files that set a list of patterns into the temprary tree

        @param sourcedir: source directory that the patterns are relative (must be absolute)
        @param patterns: list of patterns. These can contain shell-style '*' globs
        @param directory: directory put files into (relative to the top of the temporary tree)
        @param attributes: attributes passed to add_file() for each file

        """

        for f in patterns:
            absf = os.path.join(sourcedir, f)
            if f.find('*') >= 0:
                for ff in glob.iglob(absf):
                    relative = ff[len(sourcedir) + 1:]
                    if os.path.isdir(ff):
                        self.add_files_from_directory(ff, os.path.join(directory, relative), **attributes)
                    else:
                        destdir = os.path.join(directory, os.path.dirname(relative))
                        self.add_file(ff, destdir, **attributes)
            elif os.path.isdir(absf):
                self.add_files_from_directory(absf, os.path.join(directory, f), **attributes)
            else:
                destdir = os.path.join(directory, os.path.dirname(f))
                self.add_file(absf, destdir, **attributes)

    def add_external_module(self, module_name, directory, **attributes):
        """
        Add files from a Python module in the current Python path into the temporary tree

        If the python module is a package, all files in the package directory are added;
        as well as Python files, byte-code compiled python files, and shared libraries,
        this might include data files, examples, and so forth.

        @param module_name: name of the module to import
        @param directory: directory to copy module into (relative to treedir)
        @param attributes: attributes passed to add_file() for each file

        """

        mod = __import__(module_name)
        f = mod.__file__
        if f.endswith('__init__.pyc') or f.endswith('__init__.pyo') or f.endswith('__init__.py'):
            dir = os.path.dirname(f)
            # We include tests/ because with test data, they can be huge
            self.add_files_from_directory(dir, os.path.join(directory, os.path.basename(dir)),
                                          exclude=[re.compile('tests$')],
                                          **attributes)
        else:
            if f.endswith('.pyc') or f.endswith('.pyo'):
                # Don't worry about getting the compiled files, we'll recompile anyways
                f = f[:-3] + "py"
            self.add_file(f, directory, **attributes)

    def add_files_from_am(self, relative, directory, **attributes):
        """
        Add files listed in a Makefile.am into the temporary tree

        The files that are added are files that are listed as _DATA or _PYTHON.
        Recursion is done via SUBDIRS. automake conditionals are ignored.

        @param relative: path relative to the Reinteract source topdir of the
          directory where the Makefile.am lives
        @param directory: directory to copy files into (relative to tempory tree)
        @param attributes: attributes passed to add_file() for each file

        """

        am_file = os.path.join(self.topdir, relative, 'Makefile.am')
        am_parser = AMParser(am_file,
           {
                'bindir' : 'bin',
                'docdir' : 'doc',
                'examplesdir' : 'examples',
                'pkgdatadir' : '.',
                'datadir' : '.',
                'pythondir' : 'python',
                'REINTERACT_PACKAGE_DIR' : 'python/reinteract',

                # Some config variables irrelevant for our purposes
                'PYTHON_INCLUDES' : '',
                'PYTHON_LIBS' : '',
                'WRAPPER_CFLAGS' : ''
           })
        if relative == '':
            self.main_am = am_parser

        for k, v in am_parser.iteritems():
            if k.endswith("_DATA"):
                base = k[:-5]
                dir = am_parser[base + 'dir']
                for x in v.split():
                    self.add_file(os.path.join(relative, x), os.path.join(directory, dir), **attributes)
            elif k.endswith("_PYTHON"):
                base = k[:-7]
                dir = am_parser[base + 'dir']
                for x in v.split():
                    self.add_file(os.path.join(relative, x), os.path.join(directory, dir), **attributes)

        if 'SUBDIRS' in am_parser:
            for subdir in am_parser['SUBDIRS'].split():
                if subdir == '.':
                    continue
                self.add_files_from_am(os.path.join(relative, subdir), directory, **attributes)


    def compile_python(self):
        """
        Byte-compile all Python files in the tree to .pyc and .pyo
        """

        # I'm not really sure that there is a point in having the .pyc files distributed
        # but it matches what distutils and Fedora RPM packaging do.
        check_call(['python', os.path.join(self.topdir, 'tools', 'compiledir.py'), self.treedir])
        check_call(['python', "-O", os.path.join(self.topdir, 'tools', 'compiledir.py'), self.treedir])

    def get_file_attributes(self, relative):
        """
        Get the attributes dictionary for a file

        @param relative: location of the file in the temporary tree

        """
        # .pyc/.pyo are added when we byte-compile the .py files, so they
        # may not be in file_attributes[], so look for the base .py instead
        # to figure out the right feature
        if relative.endswith(".pyc") or relative.endswith(".pyo"):
            relative = relative[:-3] + "py"
            # Handle byte compiled .pyw, though they don't seem to be
            # generated in practice
            if not relative in self.file_attributes:
                relative += "w"

        return self.file_attributes[relative]

    def get_version(self):
        """
        Get the Reinteract version from configure.ac
        """

        ac_file = os.path.join(self.topdir, 'configure.ac')
        f = open(ac_file, "r")
        contents = f.read()
        f.close()
        m = re.search(r'^\s*AC_INIT\s*\(\s*[A-Za-z0-9_.-]+\s*,\s*([0-9.]+)\s*\)\s*$', contents, re.MULTILINE)
        assert m
        return m.group(1)

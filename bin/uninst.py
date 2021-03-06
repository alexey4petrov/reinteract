#!/usr/bin/env python
#
# Copyright 2007 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import os
import re
import subprocess
import sys

script_path = os.path.realpath(os.path.abspath(sys.argv[0])).decode("UTF-8")
topdir = os.path.dirname(os.path.dirname(script_path))
libdir = os.path.join(topdir, 'lib')
builderdir = os.path.join(topdir, 'dialogs')
examplesdir = os.path.join(topdir, 'examples')
icon_file = os.path.join(topdir, 'data', 'Reinteract.ico')

try:
    # Get the git description of the current commit, e.g.
    # REINTERACT_0_4_8-3-gac3e15d
    gitdir = os.path.join(topdir, ".git").encode("UTF-8")
    version = subprocess.Popen(["git", "describe"],
                               env={'GIT_DIR': gitdir},
                               stdout=subprocess.PIPE).communicate()[0]
    # Transform REINTERACT_0_4_8 into 0.4.8
    version = re.sub("^REINTERACT_", "", version)
    version = re.sub("_", ".", version)
except OSError:
    version = None

sys.path[0:0] = [libdir]

import reinteract
from reinteract.global_settings import global_settings

global_settings.dialogs_dir = builderdir
global_settings.examples_dir = examplesdir
global_settings.icon_file = icon_file
global_settings.version = version

import reinteract.main
reinteract.main.main()

################################################################################
# We're done with the real work, but for debugging purposes, close all windows
# and check that everything gets freed

from reinteract.application import application
application.close_all_windows(confirm_discard=False, wait_for_execution=False)
application.free_caches()

if len(application.windows) > 0:
    print "Some worksheets still executing, skipping leak checks."
    sys.exit(0)

# If an exception occurs and is printed with PyErr_Print() and ignored
# (say it occurs inside a signal handler), Python saves information about
# it in global variables, that will confuse our leak detection.

sys.last_type = None
sys.last_value = None
sys.last_traceback = None

application = None

import reinteract.preferences_dialog
reinteract.preferences_dialog.cleanup()

from reinteract.gc_utils import gc_idle_flush, dump_live_gobjects

gc_idle_flush()
dump_live_gobjects()


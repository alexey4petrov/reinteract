# Copyright 2008 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

def assert_equals(result, expected):
    if result != expected:
        raise AssertionError("Got %r, expected %r" % (result, expected))

def adjust_environment():
    import os, sys
    scriptname = sys.argv[0]
    script_path = os.path.realpath(os.path.abspath(scriptname)).decode("UTF-8")
    curdir = os.path.dirname(os.path.dirname(script_path))
    topdir = os.path.dirname(curdir)

    builderdir = os.path.join(topdir, 'dialogs')
    examplesdir = os.path.join(topdir, 'examples')
    icon_file = os.path.join(topdir, 'data', 'Reinteract.ico')

    from global_settings import global_settings
    global_settings.dialogs_dir = builderdir
    global_settings.examples_dir = examplesdir
    global_settings.icon_file = icon_file

    import stdout_capture
    stdout_capture.init()

    import gobject
    gobject.threads_init()

    if os.path.basename(scriptname) != 'py.test' :
        libdir = os.path.join(topdir, 'lib')
        sys.path.insert( 1 , libdir )
        pass
                                   
    return topdir


########################################################################

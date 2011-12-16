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

    if os.path.basename(scriptname) != 'py.test' :
        script_path = os.path.realpath(os.path.abspath(scriptname)).decode("UTF-8")
        topdir = os.path.dirname(os.path.dirname(script_path))
        libdir = os.path.join(topdir, 'lib')

        import logging
        if "-d" in sys.argv:
            logging.basicConfig(level=logging.DEBUG, format="DEBUG: %(message)s")
            pass
        pass
    else:
        topdir = os.path.dirname(sys.path[0]).decode("UTF-8")
        libdir = os.path.join(topdir, 'lib')
        pass

    if libdir != sys.path[0] :
        sys.path.insert( 0 , libdir )
        pass

    builderdir = os.path.join(topdir, 'dialogs')
    examplesdir = os.path.join(topdir, 'examples')
    icon_file = os.path.join(topdir, 'data', 'Reinteract.ico')

    from reinteract.global_settings import global_settings
    global_settings.dialogs_dir = builderdir
    global_settings.examples_dir = examplesdir
    global_settings.icon_file = icon_file

    from reinteract import stdout_capture
    stdout_capture.init()

    import gobject
    gobject.threads_init()

    return global_settings


########################################################################

#!/usr/bin/env python

########################################################################
#
# Copyright 2008-2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################


#--------------------------------------------------------------------------------------
def test_application_state_0():
    #--------------------------------------------------------------------------------------
    from test_utils import adjust_environment, assert_equals
    adjust_environment()

    from reinteract.application_state import ApplicationState, _section_name
    import tempfile, os

    #--------------------------------------------------------------------------------------
    def test_section_name(path, expected):
        section_name = _section_name(path)
        assert_equals(section_name, expected)

    test_section_name('C:\foo', 'C:\foo')
    test_section_name('foo[]', 'foo%5b%5d')

    #--------------------------------------------------------------------------------------
    f, location = tempfile.mkstemp(".state", "reinteract")
    os.close(f)
    try:
        nb_path = "C:\\Foo\\Bar"

        application_state = ApplicationState(location)
        application_state.notebook_opened(nb_path)
        nb_state = application_state.get_notebook_state(nb_path)
        nb_state.set_open_files([u"foo.rws", u"bar.rws"])
        application_state.flush()

        application_state = ApplicationState(location)

        recent_notebooks = application_state.get_recent_notebooks()
        assert_equals(len(recent_notebooks), 1)
        assert_equals(recent_notebooks[0].path, nb_path)

        nb_state = application_state.get_notebook_state(nb_path)
        assert nb_state.get_last_opened() > 0
        assert_equals(nb_state.get_open_files(), [u"foo.rws", u"bar.rws"])

    finally:
        try:
            os.remove(location)
        except:
            pass
        pass

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_application_state_0()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------

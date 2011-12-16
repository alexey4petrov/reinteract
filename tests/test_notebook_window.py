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
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    from test_utils import adjust_environment
    global_settings = adjust_environment()

    examplesdir = global_settings.examples_dir

    from reinteract.notebook import Notebook
    a_notebook = Notebook(examplesdir)

    from reinteract.notebook_window import NotebookWindow
    a_window = NotebookWindow(a_notebook)
    a_window.window.show()
    
    import gtk
    gtk.main()

    #--------------------------------------------------------------------------------------
    pass


######################################################################

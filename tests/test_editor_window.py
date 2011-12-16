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

    from reinteract.editor_window import EditorWindow
    a_window = EditorWindow()
    a_window.window.show()
    
    import gtk
    gtk.main()

    #--------------------------------------------------------------------------------------
    pass


######################################################################

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
    adjust_environment()

    from reinteract.notebook import Notebook
    from reinteract.worksheet_editor import WorksheetEditor
    an_editor = WorksheetEditor(Notebook())

    import gtk
    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_resizable(True)  
    window.connect("destroy", lambda widget : gtk.main_quit())
    window.set_title(__file__)
    window.set_border_width(0)
    window.resize(500, 500)
    
    window.add(an_editor.widget)
    window.show()

    # Create an accelerator group
    accelgroup = gtk.AccelGroup()
    # Add the accelerator group to the toplevel window
    window.add_accel_group(accelgroup)

    # Create an ActionGroup named ActionExample
    actiongroup = gtk.ActionGroup('ActionExample')

    calc_action = gtk.Action('calculate', None, None, None)
    # Connect a callback to the action
    calc_action.connect('activate', lambda w : an_editor.view.calculate())
    # Add the action to the actiongroup with an accelerator
    actiongroup.add_action_with_accel(calc_action, '<control>Return')
    # Have the action use accelgroup
    calc_action.set_accel_group(accelgroup)
    # Connect the accelerator to the action
    calc_action.connect_accelerator()

    quit_action = gtk.Action('Quit', '_Quit me!', 'Quit the Program', gtk.STOCK_QUIT)
    quit_action.connect('activate', lambda widget : gtk.main_quit())
    actiongroup.add_action_with_accel(quit_action, None)
    quit_action.set_accel_group(accelgroup)
    quit_action.connect_accelerator()

    gtk.main()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------

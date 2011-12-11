#!/usr/bin/env python

#--------------------------------------------------------------------------------------
# Copyright 2011 Alexey Petrov
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#

#--------------------------------------------------------------------------------------
def test_signals_0() :
    #--------------------------------------------------------------------------------------
    from signals import Signal

    #--------------------------------------------------------------------------------------
    class Button:
        def __init__(self):
            # Creating a signal as a member of a class
            self.sigClick = Signal()
            pass
        pass

    #--------------------------------------------------------------------------------------
    class Listener:
        LOGGER = []
        def onClick( self ) :
            Listener.LOGGER.append( "onClick " )
            pass
        def __call__( self ) :
            self.onClick()
            pass
        pass

    #--------------------------------------------------------------------------------------
    # a sample function to connect to the signal
    def listenFunction():
        listenFunction.LOGGER.append( "listenFunction" )
        pass

    listenFunction.LOGGER = []

    #--------------------------------------------------------------------------------------
    # a function that accepts arguments
    def listenWithArgs(text):
        listenWithArgs.LOGGER.append( text )
        pass

    listenWithArgs.LOGGER = []

    #--------------------------------------------------------------------------------------
    def reset_logs() :
        del Listener.LOGGER[ : ]
        del listenFunction.LOGGER[ : ]
        del listenWithArgs.LOGGER[ : ]
        pass
        
    #--------------------------------------------------------------------------------------
    def count() :
        return \
            len( Listener.LOGGER ) + \
            len( listenFunction.LOGGER ) + \
            len( listenWithArgs.LOGGER )
        
    #--------------------------------------------------------------------------------------
    b = Button()
    l = Listener()
    
    #--------------------------------------------------------------------------------------
    # Demonstrating connecting and calling signals
    b.sigClick.connect( l.onClick )

    reset_logs()
    b.sigClick()

    assert len( Listener.LOGGER ) == 1

    #--------------------------------------------------------------------------------------
    # Disconnecting all signals
    b.sigClick.disconnectAll()

    reset_logs()
    b.sigClick()

    assert len( Listener.LOGGER ) == 0

    #--------------------------------------------------------------------------------------
    # connecting multiple functions to a signal
    l2 = Listener()
    b.sigClick.connect( l.onClick )
    b.sigClick.connect( l2.onClick )

    reset_logs()
    b.sigClick()
    
    assert len( Listener.LOGGER ) == 2

    #--------------------------------------------------------------------------------------
    # disconnecting individual functions
    b.sigClick.disconnect( l.onClick )
    b.sigClick.connect( listenFunction )

    reset_logs()
    b.sigClick()
    
    assert len( Listener.LOGGER ) == 1
    assert len( listenFunction.LOGGER ) == 1

    #--------------------------------------------------------------------------------------
    # example with arguments and a local signal
    sig = Signal()
    sig.connect( listenWithArgs )

    reset_logs()
    sig( "Hello, World!" )

    assert len( listenWithArgs.LOGGER ) == 1

    #--------------------------------------------------------------------------------------
    # signals disconnecting 'method slots' automatically
    b.sigClick.disconnectAll()
    b.sigClick.connect( l.onClick )
    b.sigClick.connect( l2.onClick )
    del l2

    reset_logs()
    b.sigClick()
    
    assert len( Listener.LOGGER ) == 1

    #--------------------------------------------------------------------------------------
    # signals disconnecting 'object slots' automatically
    b.sigClick.disconnectAll()
    b.sigClick.connect( l )
    del l

    reset_logs()
    b.sigClick()
    
    assert len( Listener.LOGGER ) == 0

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_signals_0()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------

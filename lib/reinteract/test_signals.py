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
    # signals disconnecting 'lambda slots' automatically
    sig = Signal()
    sig.connect( lambda *args : listenFunction() )

    reset_logs()
    sig( "Hello, World!" )

    assert len( listenFunction.LOGGER ) == 1

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
def test_signals_1() :
    #--------------------------------------------------------------------------------------
    from signals import Signal

    #--------------------------------------------------------------------------------------
    class Container( object ) :
        def __init__( self ) :
            self._attr = 'dummy'
            self.attr_sig = Signal()
            pass

        @property
        def attr( self ) :
            return self._attr

        @attr.setter
        def attr( self, the_value ) :
            self._attr = the_value
            self.attr_sig( self, self._attr )
            pass

        pass

    #--------------------------------------------------------------------------------------
    def listener( the_container, the_attr ) :
        listener.LOGGER.append( the_attr )
        pass

    listener.LOGGER = []

    #--------------------------------------------------------------------------------------
    a_container = Container()
    a_container.attr_sig.connect( listener )

    a_container.attr = 'funny'

    assert len( listener.LOGGER ) == 1

    #--------------------------------------------------------------------------------------
    pass

#--------------------------------------------------------------------------------------
def test_signals_2() :
    #--------------------------------------------------------------------------------------
    from signals import Signal, Append

    #--------------------------------------------------------------------------------------
    class Container( object ) :
        def __init__( self ) :
            pass

        @Append( __init__ )
        def __init__( self, *args, **kwargs ) :
            self._attr = 'dummy'
            self.attr_sig = Signal()
            pass

        @property
        def attr( self ) :
            return self._attr

        @attr.setter
        def attr( self, the_value ) :
            self._attr = the_value
            self.attr_sig( self, self._attr )
            pass

        pass

    #--------------------------------------------------------------------------------------
    def listener( the_container, the_attr ) :
        listener.LOGGER.append( the_attr )
        pass

    listener.LOGGER = []

    #--------------------------------------------------------------------------------------
    a_container = Container()
    a_container.attr_sig.connect( listener )

    a_container.attr = 'funny'

    assert len( listener.LOGGER ) == 1

    #--------------------------------------------------------------------------------------
    pass

#--------------------------------------------------------------------------------------
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_signals_0()
    test_signals_1()
    test_signals_2()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------

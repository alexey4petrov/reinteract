#!/usr/bin/env python

#--------------------------------------------------------------------------------------
"""
Licensed under the Python Software Foundation License

File:    signals.py
Purpose: A signals implementation

Author:  Patrick Chasco
Created: July 26, 2005

Author:  Alexey Petrov
Modified: January 08, 2011 ( multi-threading support )
"""

#--------------------------------------------------------------------------------------
def test_signals_0() :
    #--------------------------------------------------------------------------------------
    from signals import Signal

    class Button:
        def __init__(self):
            # Creating a signal as a member of a class
            self.sigClick = Signal()

    class Listener:
        # a sample method that will be connected to the signal
        def onClick(self):
            print "onClick ", repr(self)
    
    # a sample function to connect to the signal
    def listenFunction():
        print "listenFunction"
   
    # a function that accepts arguments
    def listenWithArgs(text):
        print "listenWithArgs: ", text

    b = Button()
    l = Listener()
    
    # Demonstrating connecting and calling signals
    print
    print "should see one message"
    b.sigClick.connect(l.onClick)
    b.sigClick()

    # Disconnecting all signals
    print
    print "should see no messages"
    b.sigClick.disconnectAll()
    b.sigClick()

    # connecting multiple functions to a signal
    print
    print "should see two messages"
    l2 = Listener()
    b.sigClick.connect(l.onClick)
    b.sigClick.connect(l2.onClick)
    b.sigClick()
    
    # disconnecting individual functions
    print
    print "should see two messages"
    b.sigClick.disconnect(l.onClick)
    b.sigClick.connect(listenFunction)
    b.sigClick()
    
    # signals disconnecting automatically
    print
    print "should see one message"
    b.sigClick.disconnectAll()
    b.sigClick.connect(l.onClick)
    b.sigClick.connect(l2.onClick)
    del l2    
    b.sigClick()
    
    # example with arguments and a local signal
    print
    print "should see one message"
    sig = Signal()
    sig.connect(listenWithArgs)
    sig("Hello, World!")

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
def test_signals_1() :
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
        print "listenWithArgs: ", text
        pass

    #--------------------------------------------------------------------------------------
    b = Button()
    l = Listener()
    
    #--------------------------------------------------------------------------------------
    # Demonstrating connecting and calling signals
    b.sigClick.connect( l.onClick )
    del Listener.LOGGER[ : ]
    b.sigClick()

    assert len( Listener.LOGGER ) == 1

    #--------------------------------------------------------------------------------------
    # Disconnecting all signals
    b.sigClick.disconnectAll()
    del Listener.LOGGER[ : ]
    b.sigClick()

    assert len( Listener.LOGGER ) == 0

    #--------------------------------------------------------------------------------------
    # connecting multiple functions to a signal
    l2 = Listener()
    b.sigClick.connect( l.onClick )
    b.sigClick.connect( l2.onClick )
    del Listener.LOGGER[ : ]
    b.sigClick()
    
    assert len( Listener.LOGGER ) == 2

    #--------------------------------------------------------------------------------------
    # disconnecting individual functions
    b.sigClick.disconnect( l.onClick )
    b.sigClick.connect( listenFunction )
    del listenFunction.LOGGER[ : ]
    del Listener.LOGGER[ : ]
    b.sigClick()
    
    assert len( Listener.LOGGER ) == 1
    assert len( listenFunction.LOGGER ) == 1

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    # test_signals_0()
    test_signals_1()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------

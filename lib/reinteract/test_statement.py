#!/usr/bin/env python

########################################################################
#
# Copyright 2007-2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################


#--------------------------------------------------------------------------------------
def test_statement_0():
    from notebook import Notebook
    from worksheet import Worksheet
    from statement import Statement

    from test_utils import assert_equals

    import stdout_capture
    stdout_capture.init()

    nb = Notebook()
    worksheet = Worksheet(nb)

    def expect_result(text, result):
        s = Statement(text, worksheet)
        s.compile()
        s.execute()
        if isinstance(result, basestring):
            assert_equals(s.results[0], result)
        else:
            assert_equals(s.results, result)
            pass
        pass
    
    s = Statement('from reinteract.statement import Statement; Statement.get_current()', worksheet)
    s.compile()
    s.execute()
    print s.results

    # A bare expression should give the repr of the expression
    expect_result("'a'", repr('a'))
    expect_result("1,2", repr((1,2)))

    # Print, on the other hand, gives the string form of the expression, with
    # one result object per output line
    expect_result("print 'a'", 'a')
    expect_result("print 'a', 'b'", ['a b'])
    expect_result("print 'a\\nb'", ['a','b'])

    # Test that we copy a variable before mutating it (when we can detect
    # the mutation)
    s1 = Statement("b = [0]", worksheet)
    s1.compile()
    s1.execute()
    s2 = Statement("b[0] = 1", worksheet, parent=s1)
    s2.compile()
    s2.execute()
    s3 = Statement("b[0]", worksheet, parent=s2)
    s3.compile()
    s3.execute()
    assert_equals(s3.results[0], "1")
    
    s2a = Statement("b[0]", worksheet, parent=s1)
    s2a.compile()
    s2a.execute()
    assert_equals(s2a.results[0], "0")

    # Test __reinteract_wrappers with an unrealistic example
    s1 = Statement("__reinteract_wrappers = [ lambda x: 2 ]", worksheet)
    s1.compile()
    s1.execute()
    s2 = Statement("1", worksheet, parent=s1)
    s2.compile()
    s2.execute()
    assert_equals(s2.results[0], "2")

    # Tests of catching errors
    s1 = Statement("b = ", worksheet)
    assert_equals(s1.compile(), False)
    assert s1.error_message is not None

    s1 = Statement("b", worksheet)
    assert_equals(s1.compile(), True)
    assert_equals(s1.execute(), False)
    assert s1.error_message is not None

    # Tests of 'from __future__ import...'
    s1 = Statement("from __future__ import division", worksheet)
    s1.compile()
    assert_equals(s1.future_features, ['division'])
    s2 = Statement("from __future__ import with_statement", worksheet, parent=s1)
    s2.compile()
    assert_equals(s2.future_features, ['division', 'with_statement'])

    s1 = Statement("import  __future__", worksheet) # just a normal import
    assert_equals(s1.future_features, None)

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_statement_0()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------

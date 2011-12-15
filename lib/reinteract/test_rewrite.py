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
def test_rewrite_0():
    from rewrite import Rewriter, UnsupportedSyntaxError
    from test_utils import assert_equals

    import copy
    import re

    def rewrite_and_compile(code, output_func_name=None, future_features=None, print_func_name=None, encoding="utf8"):
        return Rewriter(code, encoding, future_features).rewrite_and_compile(output_func_name, print_func_name)

    #
    # Test that our intercepting of bare expressions to save the output works
    #
    def test_output(code, expected):
        compiled, _ = rewrite_and_compile(code, output_func_name='reinteract_output')
        
        test_args = []
        def set_test_args(*args): test_args[:] = args

        class Builder:
            def __init__(self, arg=None):
                self.arg = arg

            def __enter__(self):
                return self.arg

            def __exit__(self, exception_type, exception_value, traceback):
                pass

        scope = { 'reinteract_output': set_test_args, '__reinteract_builder': Builder }

        exec compiled in scope

        if tuple(test_args) != tuple(expected):
            raise AssertionError("Got '%s', expected '%s'" % (test_args, expected))

    test_output('a=3', ())
    test_output('1', (1,))
    test_output('1,2', (1,2))
    test_output('1;2', (2,))
    test_output('a=3; a', (3,))
    test_output('def x():\n    1\ny = x()', ())
    test_output('class X():\n    1\n    pass\nx = X()', ())

    #
    # Test our build "keyword"
    #
    test_output('build list() as l:\n    l.append(1)', ([1],))
    test_output('build list():\n    pass', ([],))
    test_output('build as l:\n    l = 42', (42,))
    test_output('build:\n    pass', (None,))

    #
    # Test that our intercepting of print works
    #
    def test_print(code, expected):
        compiled, _ = rewrite_and_compile(code, print_func_name='reinteract_print')
        
        test_args = []
        def set_test_args(*args): test_args[:] = args
        scope = { 'reinteract_print': set_test_args }

        exec compiled in scope

        if tuple(test_args) != tuple(expected):
            raise AssertionError("Got '%s', expected '%s'" % (test_args, expected))

    test_print('a=3', ())
    test_print('print 1', (1,))
    test_print('print 1,2', (1,2))
    test_print('print "",', ("",))
    test_print('for i in [0]: print i', (0,))
    test_print('import sys; print >>sys.stderr, "",', ())

    #
    # Test catching possible mutations of variables
    #
    def test_mutated(code, expected, prepare=None, assert_old=None, assert_new=None):
        compiled, mutated = rewrite_and_compile(code)

        #
        # Basic test - check the root and description for the returned list of mutations
        #
        mutated_root_desc = sorted(((root, description) for (root, description, _) in mutated))

        # Extract the root from a description (just take the first word)
        def expand_root_desc(description):
            m = re.match(r"([a-zA-Z_0-9]+)", description)
            return m.group(1), description

        expected_root_desc = sorted((expand_root_desc(x) for x in expected))

        if tuple(mutated_root_desc) != tuple(expected_root_desc):
            raise AssertionError("Got '%s', expected '%s'" % (mutated, expected))

        # More complex test
        #
        #  a) create old scope, execute 'prepare' in it
        #  b) copy old scope, execute each copy statement
        #  c) execute the code
        #  c) run assertion checks in old and new scope

        if prepare:
            old_scope = { '__copy' : copy.copy }
            exec prepare in old_scope
            new_scope = dict(old_scope)

            for _, _, copy_code in mutated:
                exec copy_code in new_scope

            exec compiled in new_scope

            old_ok = eval(assert_old, old_scope)
            if not old_ok:
                raise AssertionError("Old scope assertion '%s' failed" % assert_old)
            new_ok = eval(assert_new, new_scope)
            if not new_ok:
                raise AssertionError("New scope assertion '%s' failed" % assert_new)

    test_mutated('a[0] = 1', ('a',),
                 'a = [2]', 'a[0] == 2', 'a[0] == 1')
    test_mutated('a[0], b[0] = 1, 2', ('a', 'b'),
                 'a,b = [2],[1]', 'a[0],b[0] == 2,1', 'a[0],b[0] == 1,2')
    test_mutated('a[0], _ = 1', ('a'))
    test_mutated('a[0], b[0] = c[0], d[0] = 1, 2', ('a', 'b', 'c', 'd'))
    test_mutated('a[0][1] = 1', ('a', 'a[...]'),
                 'a = [[0,2],1]', 'a[0][1] == 2', 'a[0][1] == 1')

    # This isn't fully right - in the new scope b should be [1], not []
    test_mutated('a[0].append(1)', ('a', 'a[...]'),
                 'b = []; a = [b]',
                 'b == [] and a == [b]', 'b == [] and a == [[1]]')

    test_mutated('a += 1', ('a',))
    test_mutated('a[0] += 1', ('a', 'a[...]'))

    prepare = """
class A:
    def __init__(self):
        self.b = 1
    def addmul(self, x,y):
        self.b += x * y
    def get_a(self):
        return self.a
    pass
a = A()
a.a = A()
"""

    test_mutated('a.b = 2', ('a',),
                 prepare, 'a.b == 1', 'a.b == 2')
    test_mutated('a.b = 2', ('a',),
                 prepare, 'a.b == 1', 'a.b == 2')
    test_mutated('a.a.b = 2', ('a','a.a'),
                 prepare, 'a.a.b == 1', 'a.a.b == 2')
    test_mutated('a.a.b += 1', ('a','a.a','a.a.b'),
                 prepare, 'a.a.b == 1', 'a.a.b == 2')

    test_mutated('a.addmul(1,2)', ('a',),
                 prepare, 'a.b == 1', 'a.b == 3')
    test_mutated('a.a.addmul(1,2)', ('a', 'a.a'),
                 prepare, 'a.a.b == 1', 'a.a.b == 3')

    # We exempt some methods as being most likely getters.
    test_mutated('a.get_a()', ())
    test_mutated('a.hasA()', ())
    test_mutated('a.isa()', ())

    # These don't actually work properly since we don't know to copy a.a
    # So we just check the descriptions and not the execution
    #
    test_mutated('a.get_a().b = 2', ('a.get_a(...)',))
    test_mutated('a.get_a().a.b = 2', ('a.get_a(...).a',))

    # Tests of skipping mutations when the mutations are actually of
    # local variables
    test_mutated('def f(x):\n    x[1] = 2\n', ())
    test_mutated('def f(y):\n    x = [1]\n    x[1] = 2\n', ())
    test_mutated('def f(x):\n    def g(x):\n        pass', ())
    test_mutated('def f(x):\n    import g', ())
    test_mutated('def f(x):\n    from m import g', ())
    test_mutated('def f(x):\n    from m import g as h\n    h[2] = 3', ())
    test_mutated('class X:\n    x = [1]\n    x[1] = 2\n', ())
    test_mutated('def f(x):\n    class C:\n        pass', ())
    test_mutated('def f((x,)):\n    x[1] = 2\n', ())
    test_mutated('def f(((x,),)):\n    x[1] = 2\n', ())

    # But these are global mutations
    test_mutated('class X:\n    x[1] = 2\n', ('x'))
    test_mutated('class X:\n    global x\n    x[1] = 2\n    x = [1]\n', ('x'))

    # Trying to mutate a global variable inside a function is an error

    def test_unsupported_syntax(code):
        caught_exception = False
        try:
            rewrite_and_compile(code)
        except UnsupportedSyntaxError, e:
            caught_exception = True
        assert_equals(caught_exception, True)

    test_unsupported_syntax('def f(x):\n    y[1] = 2\n')
    test_unsupported_syntax('def f(x):\n    global g\n    def g(x):\n        pass')
    test_unsupported_syntax('def f(x):\n    global C\n    class C:\n        pass')

    # This binds y locally
    test_mutated('def f(x):\n    [y for y in (1,2,3)]\n    y[1] = 2\n', ())
    # But here the assignments to y are in nested scopes
    test_unsupported_syntax('def f(x):\n    (y for y in (1,2,3))\n    y[1] = 2\n')
    test_unsupported_syntax('def f(x):\n    lambda x: [y for y in (1,2,3)]\n    y[1] = 2\n')

    # Tests of 'overwrites' - our tracking of when a variable is overwritten
    # before it's mutated, so the pre-statement value doesn't require a copy.

    # Different ways to overwrite the old value of a name
    test_mutated('build [1] as a:\n    a[0] = 2', ())
    test_mutated('try:\n     pass\nexcept ValueError, a:\n    a[0] = 2', ())
    test_mutated('build:\n    def a(): pass\n    a.b = 2', ())
    test_mutated('build:\n    class A: pass\n    A.b = 2', ())
    test_mutated('for x in [[1]]:    x[0] = 2', ())
    test_mutated('for x, y in [[1]]:    x[0] = 2', ())
    test_mutated('build:\n    import sys\n    sys.b = 1', ())
    test_mutated('build:\n    import sys as a\n    a.b = 1', ())
    test_mutated('build:\n    from sys import a\n    a.b = 1', ())
    test_mutated('build:\n    from sys import b as a\n    a.b = 1', ())
    test_mutated('build:\n    from sys import *\n    a.b = 1', ('a')) # pragmatic

    # Different control flow expressions
    test_mutated('build:\n    a = [1]\n    a[0] = 2', ())
    test_mutated('build:\n    if foo():\n        a = [1]\n    a[0] = 2', ('a'))
    test_mutated('build:\n    if foo():\n        a = [1]\n        a[0] = 2', ())
    test_mutated('build:\n    if foo():\n        a = [1]\n    else:\n        a = [3]\n    a[0] = 2', ())
    test_mutated('build:\n    while foo():\n        a = [1]\n    a[0] = 2', ('a'))
    test_mutated('build:\n    while foo():\n        a = [1]\n        a[0] = 2', ())
    test_mutated('build:\n    while foo():\n        a = [1]\n    else:\n        a[0] = 2', ('a'))
    test_mutated('build:\n    for i in xrange(0, foo()):\n        a = [1]\n    a[0] = 2', ('a'))
    test_mutated('build:\n    for i in xrange(0, foo()):\n        a = [1]\n        a[0] = 2', ())
    test_mutated('build:\n    for i in xrange(0, foo()):\n        a = [1]\n    else:\n        a[0] = 2', ('a'))
    test_mutated('build:\n    try:\n         a = [1]\n    except:        pass\n    a[0] = 2', ('a'))
    test_mutated('build:\n    try:\n         a = [1]\n         a[0] = 2\n    except:        pass', ())
    test_mutated('build:\n    try:\n         pass\n    except:\n        a = [1]\n    a[0] = 2', ('a'))
    test_mutated('build:\n    try:\n         pass\n    except:\n        a = [1]\n        a[0] = 2', ())
    test_mutated('build:\n    try:\n         a = [1]\n    finally:        pass\n    a[0] = 2', ('a'))
    test_mutated('build:\n    try:\n         a = [1]\n         a[0] = 2\n    finally:        pass', ())
    test_mutated('build:\n    try:\n         pass\n    finally:\n        a = [1]\n    a[0] = 2', ())
    test_mutated('build:\n    try:\n         pass\n    finally:\n        a = [1]\n        a[0] = 2', ())

    #
    # Test handling of encoding
    #
    def test_encoding(code, expected, encoding=None):
        if encoding is not None:
            compiled, _ = rewrite_and_compile(code, encoding=encoding, output_func_name='reinteract_output')
        else:
            compiled, _ = rewrite_and_compile(code, output_func_name='reinteract_output')
        
        test_args = []
        def set_test_args(*args): test_args[:] = args
        scope = { 'reinteract_output': set_test_args }

        exec compiled in scope

        if test_args[0] != expected:
            raise AssertionError("Got '%s', expected '%s'" % (test_args[0], expected))

    test_encoding(u"u'\u00e4'".encode("utf8"), u'\u00e4')
    test_encoding(u"u'\u00e4'", u'\u00e4')
    test_encoding(u"u'\u00e4'".encode("iso-8859-1"), u'\u00e4', "iso-8859-1")

    #
    # Test import detection
    #

    def get_imports(code):
        rewriter = Rewriter(code)
        rewriter.rewrite_and_compile()
        return rewriter.get_imports()

    def test_imports(code, referenced):
        imports = get_imports(code)
        for module in referenced:
            if not imports.module_is_referenced(module):
                raise AssertionError("'%s': %s should be referenced and isn't",
                                     code, referenced)

    assert_equals(get_imports('a + 1'), None)
    test_imports('import re', ['re'])
    test_imports('import re as r', ['re'])
    test_imports('import re, os as o', ['re', 'os'])

    test_imports('from re import match', ['re'])
    test_imports('from re import match as m', ['re'])
    test_imports('from re import match as m, sub as s', ['re'])
    test_imports('from re import (match as m, sub as s)', ['re'])
    test_imports('from re import *', ['re'])

    assert_equals(get_imports('from __future__ import division').get_future_features(), set(['division']))

    #
    # Test passing in future_features to use in compilation
    #

    scope = {}
    compiled, _ = rewrite_and_compile('a = 1/2', future_features=['with_statement', 'division'])
    exec compiled in scope
    assert scope['a'] == 0.5

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_rewrite_0()

    #--------------------------------------------------------------------------------------
    pass


#--------------------------------------------------------------------------------------

#!/usr/bin/env python

######################################################################
#
# Copyright 2007-2011 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

def test_shell_buffer() :
    # The tests we include here are tests of the interaction of editing
    # with results. Results don't appear inline in a Worksheet, so these
    # tests have to be here rather than with Worksheet. Almost all other
    # testing is done in Worksheet.

    from shell_buffer import ShellBuffer, ADJUST_NONE, _forward_line
    from chunks import StatementChunk, BlankChunk, CommentChunk

    import sys, gobject
    import reunicode

    gobject.threads_init()

    from notebook import Notebook

    if "-d" in sys.argv:
        logging.basicConfig(level=logging.DEBUG, format="DEBUG: %(message)s")

    from StringIO import StringIO

    import stdout_capture
    stdout_capture.init()

    buf = ShellBuffer(Notebook())

    def insert(line, offset, text):
        i = buf.get_iter_at_line_offset(line, offset)
        buf.insert_interactive(i, text, True)

    def delete(start_line, start_offset, end_line, end_offset):
        i = buf.get_iter_at_line_offset(start_line, start_offset)
        j = buf.get_iter_at_line_offset(end_line, end_offset)
        buf.delete_interactive(i, j, True)

    def calculate():
        buf.worksheet.calculate(True)

    def clear():
        buf.worksheet.clear()

    def expect(expected):
        si = StringIO()
        i = buf.get_start_iter()
        while True:
            end = i.copy()
            if not end.ends_line():
                end.forward_to_line_end()
            text = reunicode.decode(buf.get_slice(i, end))

            line, _ = buf.iter_to_pos(i, adjust=ADJUST_NONE)
            if line is not None:
                chunk = buf.worksheet.get_chunk(line)
            else:
                chunk = None

            if chunk and isinstance(chunk, StatementChunk):
                if line == chunk.start:
                    si.write(">>> ")
                else:
                    si.write("... ")

            si.write(text)

            if _forward_line(i):
                si.write("\n")
            else:
                break

        result = si.getvalue()
        if not result == expected:
            raise AssertionError("\nGot:\n%s\nExpected:\n%s" % (result, expected))

    # Calculation resulting in result chunks
    insert(0, 0, "1 \\\n + 2\n3\n")
    calculate()
    expect(""">>> 1 \\
...  + 2
3
>>> 3
3
""")

    # Check that splitting a statement with a delete results in the
    # result chunk being moved to the last line of the first half
    delete(1, 0, 1, 1)
    expect(""">>> 1 \\
3
>>> + 2
>>> 3
3
""")

    # Editing a line with an existing error chunk to fix the error
    clear()

    insert(0, 0, "a\na = 2")
    calculate()

    insert(0, 0, "2")
    delete(0, 1, 0, 2)
    calculate()
    expect(""">>> 2
2
>>> a = 2""")

    # Test an attempt to join a ResultChunk onto a previous chunk; should join
    # the line with the following line, moving the result chunk
    clear()

    insert(0, 0, "1\n");
    calculate()
    expect(""">>> 1
1
""")

    delete(0, 1, 1, 0)
    expect(""">>> 1
1""")

    # Test an attempt to join a chunk onto a previous ResultChunk, should move
    # the ResultChunk and do the modification
    clear()
    expect("")

    insert(0, 0, "1\n2\n");
    calculate()
    expect(""">>> 1
1
>>> 2
2
""")
    delete(1, 1, 2, 0)
    expect(""">>> 12
1
""")

    # Test inserting random text inside a result chunk, should ignore
    clear()

    insert(0, 0, "1\n2");
    calculate()
    expect(""">>> 1
1
>>> 2
2""")
    insert(1, 0, "foo")
    expect(""">>> 1
1
>>> 2
2""")


    # Calculation resulting in a multi-line result change
    clear()

    insert(0, 0, "for i in range(0, 3): print i")
    calculate()
    expect(""">>> for i in range(0, 3): print i
0
1
2""")

    # Test deleting a range containing both results and statements
    clear()

    insert(0, 0, "1\n2\n3\n4\n")
    calculate()
    expect(""">>> 1
1
>>> 2
2
>>> 3
3
>>> 4
4
""")

    delete(2, 0, 5, 0)
    expect(""">>> 1
1
>>> 4
4
""")

    # Inserting an entire new statement in the middle
    insert(2, 0, "2.5\n")
    expect(""">>> 1
1
>>> 2.5
>>> 4
4
""")
    calculate()
    expect(""">>> 1
1
>>> 2.5
2.5
>>> 4
4
""")

    # Check that inserting a blank line at the beginning of a statement leaves
    # the result behind
    insert(2, 0, "\n")
    expect(""">>> 1
1

>>> 2.5
2.5
>>> 4
4
""")

    # Test deleting a range including a result and joining two statements
    clear()
    insert(0, 0, "12\n34")
    calculate()
    expect(""">>> 12
12
>>> 34
34""")
    delete(0, 1, 2, 1)
    expect(""">>> 14
12""")

    # Test a deletion that splits the buffer into two (invalid) pieces
    clear()
    insert(0, 0, "try:\n    a = 1\nfinally:\n    print 'Done'")
    calculate()
    expect(""">>> try:
...     a = 1
... finally:
...     print 'Done'
Done""")
    delete(2, 7, 2, 8)
    calculate()
    expect(""">>> try:
...     a = 1
invalid syntax
>>> finally
...     print 'Done'
invalid syntax""")

    # Try an insertion that combines the two pieces and makes them valid
    # again (combining across the error result chunk)
    insert(3, 7, ":")
    calculate()
    expect(""">>> try:
...     a = 1
... finally:
...     print 'Done'
Done""")

    # Test an undo of an insert that caused insertion of result chunks
    clear()

    insert(0, 0, "2\n")
    expect(""">>> 2
""")
    calculate()
    expect(""">>> 2
2
""")
    insert(0, 0, "1\n")
    calculate()
    buf.worksheet.undo()
    expect(""">>> 2
2
""")

    # Test insertion of WarningResult

    clear()

    insert(0, 0, """class A(object):
    def __copy__(self): raise RuntimeError("Can't copy")
    def __repr__(a): return 'A()'
    def foo(x): return x
a = A()
a.foo()""")
    calculate()
    expect(""">>> class A(object):
...     def __copy__(self): raise RuntimeError("Can't copy")
...     def __repr__(a): return 'A()'
...     def foo(x): return x
>>> a = A()
>>> a.foo()
'a' apparently modified, but can't copy it
A()""")


######################################################################
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_shell_buffer()

    #--------------------------------------------------------------------------------------
    pass


######################################################################

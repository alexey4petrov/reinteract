#!/usr/bin/env python

######################################################################
#
# Copyright 2008-2009 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
######################################################################


def test_worksheet() :
    from chunks import StatementChunk, BlankChunk, CommentChunk
    from notebook import Notebook, NotebookFile
    from worksheet import Worksheet, _debug

    import sys, gobject

    if "-d" in sys.argv:
        logging.basicConfig(level=logging.DEBUG, format="DEBUG: %(message)s")

    gobject.threads_init()

    import stdout_capture
    stdout_capture.init()

    S = StatementChunk
    B = BlankChunk
    C = CommentChunk

    #--------------------------------------------------------------------------------------
    def compare(l1, l2):
        if len(l1) != len(l2):
            return False

        for i in xrange(0, len(l1)):
            e1 = l1[i]
            e2 = l2[i]

            if type(e1) != type(e2) or e1.start != e2.start or e1.end != e2.end:
                return False

        return True

    #--------------------------------------------------------------------------------------
    worksheet = Worksheet(Notebook())

    #--------------------------------------------------------------------------------------
    def expect(expected):
        chunks = [ x for x in worksheet.iterate_chunks() ]
        if not compare(chunks, expected):
            raise AssertionError("\nGot:\n   %s\nExpected:\n   %s" % (chunks, expected))

    #--------------------------------------------------------------------------------------
    def expect_text(expected, start_line=0, start_offset=0, end_line=-1, end_offset=-1):
        text = worksheet.get_text(start_line, start_offset, end_line, end_offset)
        if (text != expected):
            raise AssertionError("\nGot:\n   '%s'\nExpected:\n   '%s'" % (text, expected))

    #--------------------------------------------------------------------------------------
    def expect_doctests(expected, start_line, end_line):
        text = worksheet.get_doctests(start_line, end_line)
        if (text != expected):
            raise AssertionError("\nGot:\n   '%s'\nExpected:\n   '%s'" % (text, expected))

    #--------------------------------------------------------------------------------------
    def expect_results(expected):
        results = [ (x.results if isinstance(x,StatementChunk) else None) for x in worksheet.iterate_chunks() ]
        if (results != expected):
            raise AssertionError("\nGot:\n   '%s'\nExpected:\n   '%s'" % (results, expected))

    #--------------------------------------------------------------------------------------
    def insert(line, offset, text):
        worksheet.insert(line, offset, text)

    #--------------------------------------------------------------------------------------
    def delete(start_line, start_offset, end_line, end_offset):
        worksheet.delete_range(start_line, start_offset, end_line, end_offset)

    #--------------------------------------------------------------------------------------
    def calculate():
        worksheet.calculate(wait=True)

    #--------------------------------------------------------------------------------------
    def clear():
        worksheet.clear()

    #--------------------------------------------------------------------------------------
    def chunk_label(chunk):
        if chunk.end - chunk.start == 1:
            return "[%s]" % chunk.start
        else:
            return "[%s:%s]" % (chunk.start, chunk.end)

    #--------------------------------------------------------------------------------------
    class CI:
        def __init__(self, start, end):
            self.start = start
            self.end = end

        def __eq__(self, other):
            if not isinstance(other, CI):
                return False

            return self.start == other.start and self.end == other.end

        def __repr__(self):
            return "CI(%s, %s)" % (self.start, self.end)

    #--------------------------------------------------------------------------------------
    class CC:
        def __init__(self, start, end, changed_lines):
            self.start = start
            self.end = end
            self.changed_lines = changed_lines

        def __eq__(self, other):
            if not isinstance(other, CC):
                return False

            return self.start == other.start and self.end == other.end and self.changed_lines == other.changed_lines

        def __repr__(self):
            return "CC(%s, %s, %s)" % (self.start, self.end, self.changed_lines)

    #--------------------------------------------------------------------------------------
    class CD:
        def __eq__(self, other):
            if not isinstance(other, CD):
                return False

            return True

        def __repr__(self):
            return "CD()"

    #--------------------------------------------------------------------------------------
    class CSC:
        def __init__(self, start, end):
            self.start = start
            self.end = end

        def __eq__(self, other):
            if not isinstance(other, CSC):
                return False

            return self.start == other.start and self.end == other.end

        def __repr__(self):
            return "CSC(%s, %s)" % (self.start, self.end)

    #--------------------------------------------------------------------------------------
    class CRC:
        def __init__(self, start, end):
            self.start = start
            self.end = end

        def __eq__(self, other):
            if not isinstance(other, CRC):
                return False

            return self.start == other.start and self.end == other.end

        def __repr__(self):
            return "CRC(%s, %s)" % (self.start, self.end)

        pass


    #--------------------------------------------------------------------------------------
    class Logger :
        def __init__( self ) :
            self._log = []
            pass

        def on_chunk_inserted( self, worksheet, chunk ) :
            _debug("...Chunk %s inserted", chunk_label(chunk))
            self._log.append(CI(chunk.start, chunk.end))
            pass

        def on_chunk_changed( self, worksheet, chunk, changed_lines ) :
            _debug("...Chunk %s changed", chunk_label(chunk))
            self._log.append(CC(chunk.start, chunk.end, changed_lines))
            pass

        def on_chunk_deleted( self, worksheet, chunk ) :
            _debug("...Chunk %s deleted", chunk_label(chunk))
            self._log.append(CD())
            pass

        def on_chunk_status_changed( self, worksheet, chunk ) :
            _debug("...Chunk %s status changed", chunk_label(chunk))
            self._log.append(CSC(chunk.start, chunk.end))
            pass

        def on_chunk_results_changed( self, worksheet, chunk ) :
            _debug("...Chunk %s results changed", chunk_label(chunk))
            self._log.append(CRC(chunk.start, chunk.end))
            pass

        def clear_log( self ) :
            self._log = []
            pass

        def expect_log( self, expected ) :
            if self._log != expected:
                raise AssertionError("\nGot:\n   '%s'\nExpected:\n   '%s'" % (log, expected))
            self.clear_log()
            pass
        pass


    #--------------------------------------------------------------------------------------
    a_logger = Logger()
    worksheet.chunk_inserted.connect( a_logger.on_chunk_inserted )
    worksheet.connect('chunk-changed', a_logger.on_chunk_changed)
    worksheet.connect('chunk-deleted', a_logger.on_chunk_deleted)
    worksheet.connect('chunk-status-changed', a_logger.on_chunk_status_changed)
    worksheet.connect('chunk-results-changed', a_logger.on_chunk_results_changed)

    # Insertions
    insert(0, 0, "11\n22\n33")
    expect_text("11\n22\n33")
    expect([S(0,1), S(1,2), S(2,3)])
    insert(0, 1, "a")
    expect_text("1a1\n22\n33")
    expect([S(0,1), S(1,2), S(2,3)])
    insert(1, 1, "a\na")
    expect_text("1a1\n2a\na2\n33")
    expect([S(0,1), S(1,2), S(2,3), S(3,4)])
    insert(1, 0, "bb\n")
    expect_text("1a1\nbb\n2a\na2\n33")
    expect([S(0,1), S(1,2), S(2,3), S(3,4), S(4, 5)])
    insert(4, 3, "\n")
    expect_text("1a1\nbb\n2a\na2\n33\n")
    expect([S(0,1), S(1,2), S(2,3), S(3,4), S(4, 5), B(5, 6)])

    # Deletions
    delete(4, 3, 5, 0)
    expect_text("1a1\nbb\n2a\na2\n33")
    expect([S(0,1), S(1,2), S(2,3), S(3,4), S(4, 5)])
    delete(0, 1, 0, 2)
    expect_text("11\nbb\n2a\na2\n33")
    expect([S(0,1), S(1,2), S(2,3), S(3,4), S(4, 5)])
    delete(0, 0, 1, 0)
    expect_text("bb\n2a\na2\n33")
    expect([S(0,1), S(1,2), S(2,3), S(3,4)])
    delete(1, 1, 2, 1)
    expect_text("bb\n22\n33")
    expect([S(0,1), S(1,2), S(2,3)])
    delete(2, 1, 1, 0)
    expect_text("bb\n3")
    expect([S(0,1), S(1,2)])

    # Test deleting part of a BlankChunk
    clear()
    insert(0, 0, "if True\n:    pass\n    \n")
    delete(2, 4, 3, 0)

    # Check that tracking of changes works properly when there
    # is an insertion or deletion before the change
    clear()
    insert(0, 0, "1\n2")
    worksheet.begin_user_action()
    insert(1, 0, "#")
    insert(0, 0, "0\n")
    worksheet.end_user_action()
    expect_text("0\n1\n#2")
    expect([S(0,1), S(1,2), C(2,3)])
    worksheet.begin_user_action()
    delete(2, 0, 2, 1)
    delete(0, 0, 1, 0)
    worksheet.end_user_action()
    expect([S(0,1), S(1,2)])

    # Basic tokenization of valid python
    clear()
    insert(0, 0, "1\n\n#2\ndef a():\n  3")
    expect([S(0,1), B(1,2), C(2,3), S(3,5)])

    clear()
    expect([B(0,1)])

    # Multiple consecutive blank lines
    clear()
    insert(0, 0, "1")
    insert(0, 1, "\n")
    expect([S(0,1),B(1,2)])
    insert(1, 0, "\n")
    expect([S(0,1),B(1,3)])

    # Continuation lines at the beginning
    clear()
    insert(0, 0, "# Something\n   pass")
    expect([C(0,1), S(1,2)])
    delete(0, 0, 1, 0)
    expect([S(0,1)])

    # Decorators
    clear()
    insert(0, 0, "def foo():\n    return 42")
    expect([S(0,2)])
    insert(0, 0, "@decorated\n")
    expect([S(0,3)])
    insert(0, 0, "@decorated\n")
    expect([S(0,4)])

    # decorator in the middle breaks things up
    insert(3, 0, "@decorated\n")
    expect([S(0,3), S(3,5)])
    delete(3, 0, 4, 0)
    expect([S(0,4)])

    # lonely decorator at the end of a worksheet
    clear()
    insert(0, 0, "@decorated\n# some comment\n")
    expect([S(0,1), C(1,2), B(2,3)])
    insert(2, 0, "def foo():\n    return 42")
    expect([S(0,4)])

    # Calculation
    clear()
    insert(0, 0, "1 + 1")
    calculate()
    expect_results([['2']])

    clear()
    insert(0, 0, "if True:\n    print 1\n    print 1")
    calculate()
    expect_results([['1', '1']])

    clear()
    insert(0, 0, "a = 1\nb = 2\na + b")
    calculate()
    expect_results([[], [], ['3']])
    delete(1, 4, 1, 5)
    insert(1, 4, "3")
    calculate()
    expect_results([[], [], ['4']])

    #--------------------------------------------------------------------------------------
    #
    # Test out signals and expect_log()
    #
    clear()
    a_logger.clear_log()
    insert(0, 0, "1 + 1")
    a_logger.expect_log([CD(), CI(0,1)])
    calculate()
    a_logger.expect_log([CSC(0,1), CRC(0,1)])

    insert(0, 0, "#")
    a_logger.expect_log([CD(), CI(0,1)])

    # Deleting a chunk with results
    clear()
    insert(0, 0, "1\n2")
    calculate()
    expect([S(0,1),S(1,2)])
    expect_results([['1'],['2']])
    a_logger.clear_log()
    delete(0, 0, 0, 1)
    expect([B(0,1),S(1,2)])
    a_logger.expect_log([CD(), CI(0,1), CSC(1,2)])

    # change a statement into a comment
    clear()
    insert(0, 0, "# a\nb")
    a_logger.clear_log()
    insert(1, 0, "#")
    expect([C(0,2)])
    a_logger.expect_log([CD(), CC(0,2,[1])])

    # Turning a statement into a continuation line
    clear()
    insert(0, 0, "1 \\\n+ 2\n")
    a_logger.clear_log()
    insert(1, 0, " ")
    expect([S(0,2), B(2,3)])
    a_logger.expect_log([CD(), CC(0,2,[1])])

    # And back
    delete(1, 0, 1, 1)
    expect([S(0,1), S(1,2), B(2,3)])
    a_logger.expect_log([CC(0,1,[]),CI(1,2)])

    # Shortening the last chunk in the buffer
    clear()
    insert(0, 0, "def a():\n    x = 1\n    return 1")
    delete(1, 0, 2, 0)
    expect([S(0, 2)])

    # Inserting a statement above a continuation line at the start of the buffer
    clear()
    insert(0, 0, "#def a(x):\n    return x")
    delete(0, 0, 0, 1)
    expect([S(0,2)])

    # Deleting an entire continuation line
    clear()

    insert(0, 0, "for i in (1,2):\n    print i\n    print i + 1\n")
    expect([S(0,3), B(3,4)])
    delete(1, 0, 2, 0)
    expect([S(0,2), B(2,3)])

    # Editing a continuation line, while leaving it a continuation
    clear()

    insert(0, 0, "1\\\n  + 2\\\n  + 3")
    delete(1, 0, 1, 1)
    expect([S(0,3)])

    # Test that changes that substitute text with identical
    # text counts as changes

    # New text
    clear()
    insert(0, 0, "if")
    a_logger.clear_log()
    worksheet.begin_user_action()
    delete(0, 1, 0, 2)
    insert(0, 1, "f")
    worksheet.end_user_action()
    expect([S(0,1)])
    a_logger.expect_log([CC(0,1,[0])])

    # Text from elsewhere in the buffer
    clear()
    insert(0, 0, "if\nif")
    a_logger.clear_log()
    delete(0, 1, 1, 1)
    expect([S(0,1)])
    a_logger.expect_log([CD(), CC(0,1,[0])])

    # Test that commenting out a line marks subsequent lines for recalculation
    clear()

    insert(0, 0, "a = 1\na = 2\na")
    calculate()
    insert(1, 0, "#")
    assert worksheet.get_chunk(2).needs_execute

    # Test that we don't send out '::chunk-deleted' signal for chunks for
    # which we never sent a '::chunk_inserted' signal

    clear()

    insert(0, 0, "[1]")
    a_logger.clear_log()
    worksheet.begin_user_action()
    insert(0, 2, "\n")
    worksheet.rescan()
    insert(1, 0, "    ")
    worksheet.end_user_action()
    a_logger.expect_log([CC(0,2,[0,1])])

    #
    # Undo tests
    #
    clear()

    insert(0, 0, "1")
    worksheet.undo()
    expect_text("")
    worksheet.redo()
    expect_text("1")

    # Undoing insertion of a newline
    clear()

    insert(0, 0, "1 ")
    insert(0, 1, "\n")
    calculate()
    worksheet.undo()
    expect_text("1 ")

    # Test the "pruning" behavior of modifications after undos
    clear()

    insert(0, 0, "1")
    worksheet.undo()
    expect_text("")
    insert(0, 0, "2")
    worksheet.redo() # does nothing
    expect_text("2")
    insert(0, 0, "2\n")

    # Test coalescing consecutive inserts
    clear()

    insert(0, 0, "1")
    insert(0, 1, "2")
    worksheet.undo()
    expect_text("")

    # Test grouping of multiple undos by user actions
    clear()

    insert(0, 0, "1")
    worksheet.begin_user_action()
    delete(0, 0, 0, 1)
    insert(0, 0, "2")
    worksheet.end_user_action()
    worksheet.undo()
    expect_text("1")
    worksheet.redo()
    expect_text("2")

    # Make sure that coalescing doesn't coalesce one user action with
    # only part of another
    clear()

    insert(0, 0, "1")
    worksheet.begin_user_action()
    insert(0, 1, "2")
    delete(0, 0, 0, 1)
    worksheet.end_user_action()
    worksheet.undo()
    expect_text("1")
    worksheet.redo()
    expect_text("2")

    #
    # Tests of get_text()
    #
    clear()
    insert(0, 0, "12\n34\n56")
    expect_text("12\n34\n56", -1, -1, 0, 0)
    expect_text("2\n34\n5", 0, 1, 2, 1)
    expect_text("", -1, -1, -1, -1)
    expect_text("1", 0, 0, 0, 1)
    expect_text("2\n3", 0, 1, 1, 1)
    expect_text("2\n3", 1, 1, 0, 1)

    #
    # Tests of get_doctests()
    #
    clear()
    insert(0, 0, """# A tests of doctests
def a(x):
    return x + 1

a(2)
""")
    calculate()

    expect_doctests("""# A tests of doctests
>>> def a(x):
...     return x + 1

>>> a(2)
3
""", 0, 5)

    expect_doctests(""">>> def a(x):
...     return x + 1
""", 2, 2)

    #
    # Try writing to a file, and reading it back
    #
    import tempfile, os

    clear()
    expect([B(0,1)])

    SAVE_TEST = """a = 1
a
# A comment

b = 2"""

    insert(0, 0, SAVE_TEST)
    calculate()

    handle, fname = tempfile.mkstemp(u".rws", u"reinteract_worksheet")
    os.close(handle)

    try:
        worksheet.save(fname)
        f = open(fname, "r")
        saved = f.read()
        f.close()

        if saved != SAVE_TEST:
            raise AssertionError("Got '%s', expected '%s'", saved, SAVE_TEST)

        worksheet.load(fname)
        calculate()

        expect_text(SAVE_TEST)
        expect([S(0,1), S(1,2), C(2,3), B(3,4), S(4,5)])
        expect_results([[], ['1'], None, None, []])
    finally:
        os.remove(fname)

    clear()
    expect([B(0,1)])


######################################################################
if __name__ == "__main__":
    #--------------------------------------------------------------------------------------
    test_worksheet()

    #--------------------------------------------------------------------------------------
    pass


######################################################################

# Copyright 2007-2011 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

from __future__ import with_statement

import gobject
import gtk
import logging
import pango

from custom_result import CustomResult
from chunks import StatementChunk,CommentChunk
from destroyable import Destroyable
import doc_format
from notebook import HelpResult
import reunicode
from statement import WarningResult
from style import DEFAULT_STYLE
from worksheet import Worksheet, NEW_LINE_RE

_debug = logging.getLogger("ShellBuffer").debug

# See comment in iter_copy_from.py
try:
    gtk.TextIter.copy_from
    def _copy_iter(dest, src):
        dest.copy_from(src)
except AttributeError:
    from iter_copy_from import iter_copy_from as _copy_iter

class _RevalidateIters:
    def __init__(self, buffer, *iters):
        self.buffer = buffer
        self.iters = iters

    def __enter__(self):
        self.marks = map(lambda iter: (iter, self.buffer.create_mark(None, iter, True)), self.iters)

    def __exit__(self, exception_type, exception_value, exception_traceback):
        for iter, mark in self.marks:
            _copy_iter(iter, self.buffer.get_iter_at_mark(mark))
            self.buffer.delete_mark(mark)

ADJUST_BEFORE = 0
ADJUST_AFTER = 1
ADJUST_NONE = 2

#######################################################
# GtkTextView fixups
#######################################################

# Return value of iter.forward_line() is useless "whether the iter is
# derefenceable" ... causes bugs with empty last lines where you move
# onto the last line and it is immediately not dereferenceable
def _forward_line(iter):
    """iter.forward_line() with fixed-up return value (moved to next line)"""

    line = iter.get_line()
    iter.forward_line()
    return iter.get_line() != line

# Mostly for consistency ... iter.forward_line() has more useful return value
# (moved) then backward_line
def _backward_line(iter):
    """iter.backward_line() with fixed-up return value (moved to next line)"""

    line = iter.get_line()
    iter.backward_line()
    return iter.get_line() != line

####################################################################

class ShellBuffer(Destroyable, gtk.TextBuffer):
    __gsignals__ = {
        'add-custom-result':  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT)),
        'add-sidebar-results':  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        'remove-sidebar-results':  (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        'pair-location-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT))
    }

    def __init__(self, notebook, edit_only=False):
        gtk.TextBuffer.__init__(self)

        self.worksheet = Worksheet(notebook, edit_only)
        self.worksheet.text_inserted.connect( self.on_text_inserted )
        self.worksheet.text_deleted.connect( self.on_text_deleted )
        self.worksheet.connect('lines-inserted', self.on_lines_inserted)
        self.worksheet.connect('lines-deleted', self.on_lines_deleted)
        self.worksheet.chunk_inserted.connect( self.on_chunk_inserted )
        self.worksheet.connect('chunk-changed', self.on_chunk_changed)
        self.worksheet.connect('chunk-deleted', self.on_chunk_deleted)
        self.worksheet.connect('chunk-status-changed', self.on_chunk_status_changed)
        self.worksheet.connect('chunk-results-changed', self.on_chunk_results_changed)
        self.worksheet.connect('place-cursor', self.on_place_cursor)

        style = DEFAULT_STYLE

        # If the last line of the buffer is empty, then there's no way to set a
        # paragraph style for it - this means that we can't reliably make
        # chunk.set_pixels_below() work for the last line in the buffer.
        # So, what we do is override pixels_below_lines for the whole buffer,
        # enabling gtk.TextView.set_pixels_below_lines() to be used for this.
        self.__whole_buffer_tag = self.create_tag(pixels_below_lines=0)

        self.__result_tag = style.get_tag(self, 'result')
        # Bit of a cheat - don't want to add these to StyleSpec, since they are editor specific.
        # If the spec was shared by an alias, this would do unexpected things.
        self.__result_tag.set_properties(wrap_mode=gtk.WRAP_WORD, editable=False)
        self.__warning_tag = style.get_tag(self, 'warning')
        self.__error_tag = style.get_tag(self, 'error')
        self.__error_line_tag = style.get_tag(self, 'error-line')
        # We want the recompute tag to have higher priority, so we fetch it after result_tag
        # which will result in it being defined second
        self.__status_tags = style.get_tag(self, 'recompute')
        self.__comment_tag = style.get_tag(self, 'comment')
        self.__help_tag = style.get_tag(self, 'help')

        self.__bold_tag = self.create_tag(weight=pango.WEIGHT_BOLD)

        self.__fontify_tags = {}
        for subject in style.specs:
            if isinstance(subject, int): # A token type
                self.__fontify_tags[subject] = style.get_tag(self, subject)

        self.__line_marks = [self.create_mark(None, self.get_start_iter(), True)]
        self.__line_marks[0].line = 0
        self.__in_modification_count = 0

        self.__have_pair = False
        self.__pair_mark = self.create_mark(None, self.get_start_iter(), True)

    def do_destroy(self):
        for chunk in self.worksheet.iterate_chunks():
            self.__delete_results_marks(chunk)

        self.worksheet.destroy()
        self.worksheet = None

        Destroyable.do_destroy(self)

    #######################################################
    # Utility
    #######################################################

    def __begin_modification(self):
        self.__in_modification_count += 1

    def __end_modification(self):
        self.__in_modification_count -= 1

    def __insert_results(self, chunk):
        if not isinstance(chunk, StatementChunk):
            return

        if chunk.results_start_mark or chunk.sidebar_results:
            raise RuntimeError("__insert_results called when we already have results")

        if (chunk.results is None or len(chunk.results) == 0) and chunk.error_message is None:
            return

        if chunk.error_message:
            inline_results = [ chunk.error_message ]
            sidebar_results = None
        else:
            inline_results = []
            sidebar_results = []
            for result in chunk.results:
                if hasattr(result, 'display'):
                    display = result.display
                else:
                    display = 'inline'

                if display == 'side':
                    sidebar_results.append(result)
                else:
                    inline_results.append(result)

        if sidebar_results:
            chunk.sidebar_results = sidebar_results
            self.emit("add-sidebar-results", chunk)

        if not inline_results:
            return

        self.__begin_modification()

        location = self.pos_to_iter(chunk.end - 1)
        if not location.ends_line():
            location.forward_to_line_end()

        # We don't want to move the insert cursor in the common case of
        # inserting a result right at the insert cursor
        if location.compare(self.get_iter_at_mark(self.get_insert())) == 0:
            saved_insert = self.create_mark(None, location, True)
        else:
            saved_insert = None

        self.insert(location, "\n")

        chunk.results_start_mark = self.create_mark(None, location, True)
        chunk.results_start_mark.source = chunk

        first = True
        for result in inline_results:
            if not first:
                self.insert(location, "\n")
            first = False

            if isinstance(result, basestring):
                self.insert(location, result)
            elif isinstance(result, WarningResult):
                start_mark = self.create_mark(None, location, True)
                self.insert(location, result.message)
                start = self.get_iter_at_mark(start_mark)
                self.delete_mark(start_mark)
                self.apply_tag(self.__warning_tag, start, location)
            elif isinstance(result, HelpResult):
                start_mark = self.create_mark(None, location, True)
                doc_format.insert_docs(self, location, result.arg, self.__bold_tag)
                start = self.get_iter_at_mark(start_mark)
                self.delete_mark(start_mark)
                self.apply_tag(self.__help_tag, start, location)
            elif isinstance(result, CustomResult):
                anchor = self.create_child_anchor(location)
                self.emit("add-custom-result", result, anchor)
                location = self.get_iter_at_child_anchor(anchor)
                location.forward_char() # Skip over child

        start = self.get_iter_at_mark(chunk.results_start_mark)
        self.apply_tag(self.__result_tag, start, location)
        self.apply_tag(self.__whole_buffer_tag, start, location)
        if chunk.error_message:
            self.apply_tag(self.__error_tag, start, location)
        chunk.results_end_mark = self.create_mark(None, location, True)
        chunk.results_start_mark.source = chunk

        if saved_insert is not None:
            self.place_cursor(self.get_iter_at_mark(saved_insert))
            self.delete_mark(saved_insert)

        self.__end_modification()

        if chunk.pixels_below != 0:
            self.__reset_last_line_tag(chunk)

    def __delete_results_marks(self, chunk):
        if not (isinstance(chunk, StatementChunk) and chunk.results_start_mark):
            return

        self.delete_mark(chunk.results_start_mark)
        self.delete_mark(chunk.results_end_mark)
        chunk.results_start_mark = None
        chunk.results_end_mark = None

    def __delete_inline_results(self, chunk):
        if not (isinstance(chunk, StatementChunk) and chunk.results_start_mark):
            return

        self.__begin_modification()

        start = self.get_iter_at_mark(chunk.results_start_mark)
        end = self.get_iter_at_mark(chunk.results_end_mark)
        # Delete the newline before the result along with the result
        start.backward_line()
        if not start.ends_line():
            start.forward_to_line_end()
        self.delete(start, end)
        self.__delete_results_marks(chunk)

        self.__end_modification()

        if chunk.pixels_below != 0:
            self.__reset_last_line_tag(chunk)

    def __delete_sidebar_results(self, chunk):
        if not (isinstance(chunk, StatementChunk) and chunk.sidebar_results):
            return

        chunk.sidebar_results = None
        self.emit('remove-sidebar-results', chunk)

    def __delete_results(self, chunk):
        if not isinstance(chunk, StatementChunk):
            return

        self.__delete_inline_results(chunk)
        self.__delete_sidebar_results(chunk)

    def __set_pair_location(self, location):
        changed = False
        old_location = None

        if location is None:
            if self.__have_pair:
                old_location = self.get_iter_at_mark(self.__pair_mark)
                self.__have_pair = False
                changed = True
        else:
            if not self.__have_pair:
                self.__have_pair = True
                self.move_mark(self.__pair_mark, location)
                changed = True
            else:
                old_location = self.get_iter_at_mark(self.__pair_mark)
                if location.compare(old_location) != 0:
                    self.move_mark(self.__pair_mark, location)
                    changed = True

        if changed:
            self.emit('pair-location-changed', old_location, location)

    def __calculate_pair_location(self):
        location = self.get_iter_at_mark(self.get_insert())

        # GTK+-2.10 has fractionally-more-efficient buffer.get_has_selection()
        selection_bound = self.get_iter_at_mark(self.get_selection_bound())
        if location.compare(selection_bound) != 0:
            self.__set_pair_location(None)
            return

        location = self.get_iter_at_mark(self.get_insert())
        line, offset = self.iter_to_pos(location, adjust=ADJUST_NONE)

        if line is None:
            self.__set_pair_location(None)
            return

        chunk = self.worksheet.get_chunk(line)
        if not isinstance(chunk, StatementChunk):
            self.__set_pair_location(None)
            return

        if offset == 0:
            self.__set_pair_location(None)
            return

        pair_line, pair_start = chunk.tokenized.get_pair_location(line - chunk.start, offset - 1)

        if pair_line is None:
            self.__set_pair_location(None)
            return

        pair_iter = self.pos_to_iter(chunk.start + pair_line, pair_start)
        self.__set_pair_location(pair_iter)

    def __retag_chunk(self, chunk, changed_lines, tag):
        iter = self.pos_to_iter(chunk.start)
        i = 0
        for l in changed_lines:
            while i < l:
                iter.forward_line()
                i += 1
            end = iter.copy()
            end.forward_line()
            self.remove_all_tags(iter, end)
            self.apply_tag(self.__whole_buffer_tag, iter, end)

            if tag:
                self.apply_tag(tag, iter, end)

    def __fontify_statement_chunk(self, chunk, changed_lines):
        iter = self.pos_to_iter(chunk.start)
        i = 0
        for l in changed_lines:
            while i < l:
                iter.forward_line()
                i += 1
            end = iter.copy()
            end.forward_line()
            self.remove_all_tags(iter, end)
            self.apply_tag(self.__whole_buffer_tag, iter, end)

            end = iter.copy()
            for token_type, start_index, end_index, _ in chunk.tokenized.get_tokens(l):
                tag = self.__fontify_tags[token_type]
                if tag is not None:
                    iter.set_line_offset(start_index)
                    end.set_line_offset(end_index)
                    self.apply_tag(tag, iter, end)

    def __reset_first_line_tag(self, chunk):
        first_line_start = self.pos_to_iter(chunk.start)
        first_line_end = first_line_start.copy()
        first_line_end.forward_line()
        last_line_end = self.pos_to_iter(chunk.end - 1)
        last_line_end.forward_line()

        self.remove_tag(chunk.__first_line_tag, first_line_start, last_line_end)
        self.apply_tag(chunk.__first_line_tag, first_line_start, first_line_end)

    def __reset_last_line_tag(self, chunk):
        first_line_start = self.pos_to_iter(chunk.start)

        if isinstance(chunk, StatementChunk) and chunk.results_end_mark is not None:
            last_line_end = self.get_iter_at_mark(chunk.results_end_mark)
            last_line_start = last_line_end.copy()
            last_line_end.set_line_offset(0)
        else:
            last_line_start = self.pos_to_iter(chunk.end - 1)
            last_line_end = last_line_start.copy()
            last_line_end.forward_line()

        self.remove_tag(chunk.__last_line_tag, first_line_start, last_line_end)
        self.apply_tag(chunk.__last_line_tag, last_line_start, last_line_end)

    #######################################################
    # Overrides for GtkTextView behavior
    #######################################################

    def do_begin_user_action(self):
        self.worksheet.begin_user_action()

    def do_end_user_action(self):
        self.worksheet.end_user_action()
        if not self.worksheet.in_user_action():
            self.__calculate_pair_location()

    def do_insert_text(self, location, text, text_len):
        if self.__in_modification_count > 0:
            gtk.TextBuffer.do_insert_text(self, location, text, text_len)
            return

        line, offset = self.iter_to_pos(location, adjust=ADJUST_NONE)
        if line is None:
            return

        with _RevalidateIters(self, location):
            # If we get "unsafe" text from GTK+, it will be a non-BMP character.
            # Inserting this as an escape isn't entirely unexpected and is
            # the best we can do.
            self.worksheet.insert(line, offset, reunicode.decode(text[0:text_len], escape="True"))
    def do_delete_range(self, start, end):
        if self.__in_modification_count > 0:
            gtk.TextBuffer.do_delete_range(self, start, end)
            return

        start_line, start_offset = self.iter_to_pos(start, adjust=ADJUST_AFTER)
        end_line, end_offset = self.iter_to_pos(end, adjust=ADJUST_AFTER)

        # If start and end crossed, then they were both within a result. Ignore
        # (This really shouldn't happen)
        if start_line > end_line or (start_line == end_line and start_offset > end_offset):
            return

        # If start and end ended up at the same place, then we must have been
        # trying to join a result with a adjacent text line. Treat that as joining
        # the two text lines.
        if start_line == end_line and start_offset == end_offset:
            if start_offset == 0: # Start of the line after
                if start_line > 0:
                    start_line -= 1
                    start_offset = len(self.worksheet.get_line(start_line))
            else: # End of the previous line
                if end_line < self.worksheet.get_line_count() - 1:
                    end_line += 1
                    end_offset = 0

        with _RevalidateIters(self, start, end):
            self.worksheet.delete_range(start_line, start_offset, end_line, end_offset)

    def do_mark_set(self, location, mark):
        try:
            gtk.TextBuffer.do_mark_set(self, location, mark)
        except NotImplementedError:
            # the default handler for ::mark-set was added in GTK+-2.10
            pass

        if mark != self.get_insert() and mark != self.get_selection_bound():
            return

        if not self.worksheet.in_user_action():
            self.__calculate_pair_location()

    #######################################################
    # Callbacks on worksheet changes
    #######################################################

    def on_text_inserted(self, worksheet, line, offset, text):
        self.__begin_modification()
        location = self.pos_to_iter(line, offset)

        # The inserted text may carry a set of results away from the chunk
        # that produced it. Worksheet doesn't care what we do with the
        # result chunks on an insert location, as long as the resulting
        # text (ignoring results) matches what it expects. If the
        # text doesn't start with a newline, then the chunk above is
        # necessarily modified, and we'll fix things up when we get the
        # ::chunk-changed. If the text starts with a newline, then we
        # insert after the results, since it doesn't matter. But we
        # also have to fix the cursor.

        chunk = worksheet.get_chunk(line)
        if (line == chunk.end - 1 and NEW_LINE_RE.match(text) and
            isinstance(chunk, StatementChunk) and
            offset == len(chunk.tokenized.lines[-1]) and
            chunk.results_start_mark):

            result_end = self.get_iter_at_mark(chunk.results_end_mark)
            cursor_location = self.get_iter_at_mark(self.get_insert())

            if (location.compare(cursor_location) == 0):
                self.place_cursor(result_end)

            location = result_end

        if isinstance(chunk, StatementChunk):
            chunk.error_line = None

        self.insert(location, text, -1)

        # Worksheet considers an insertion of multiple lines of text at
        # offset 0 to shift that line down. Since our line start marks
        # have left gravity and don't move, we need to fix them up.
        if offset == 0:
            count = 0
            for m in NEW_LINE_RE.finditer(text):
                count += 1

            if count > 0:
                mark = self.__line_marks[line]
                iter = self.get_iter_at_mark(mark)
                while count > 0:
                    iter.forward_line()
                    count -= 1
                self.move_mark(mark, iter)

        self.__end_modification()

    def on_text_deleted(self, worksheet, start_line, start_offset, end_line, end_offset):
        self.__begin_modification()
        start = self.pos_to_iter(start_line, start_offset)
        end = self.pos_to_iter(end_line, end_offset)

        # The range may contain intervening results; Worksheet doesn't care
        # if we delete them or not, but the resulting text in the buffer (ignoring
        # results) matches what it expects. In the normal case, we just delete
        # the results, and if they belong to a statement above, they will be added
        # back when we get the ::chunk-changed signal. There is a special case when
        # the chunk above doesn't change; when we delete from * to * in:
        #
        # 1 + 1 *
        # /2/
        # [ ... more stuff ]
        # * <empty line>
        #
        # In this case, we adjust the range to start at the end of the first result,
        # But we also have to fix up the cursor.
        #
        start_chunk = worksheet.get_chunk(start_line)
        if (isinstance(start_chunk, StatementChunk) and start_chunk.results_start_mark and
            start_line == start_chunk.end - 1 and start_offset == len(start_chunk.tokenized.lines[-1]) and
            end.get_line_offset() == 0 and end.ends_line()):

            cursor_location = self.get_iter_at_mark(self.get_insert())
            if (start.compare(cursor_location) < 0 and end.compare(cursor_location) >= 0):
                self.place_cursor(start)

            start = self.get_iter_at_mark(start_chunk.results_end_mark)
            start_line += 1

        for chunk in worksheet.iterate_chunks(start_line, end_line):
            if chunk != worksheet.get_chunk(end_line):
                if isinstance(chunk, StatementChunk):
                    chunk.error_line = None

                self.__delete_results_marks(chunk)
                self.__delete_sidebar_results(chunk)

        chunk = worksheet.get_chunk(end_line)
        if isinstance(chunk, StatementChunk):
            chunk.error_line = None

        self.delete(start, end)
        self.__end_modification()

    def on_lines_inserted(self, worksheet, start, end):
        _debug("...lines %d:%d inserted", start, end)
        if start == 0:
            iter = self.get_start_iter()
        else:
            iter = self.pos_to_iter(start - 1)
            iter.forward_line()
            while True:
                for mark in iter.get_marks():
                    if hasattr(mark, 'source'): # A result chunk!
                        iter = self.get_iter_at_mark(mark.source.results_end_mark)
                        iter.forward_line()
                        continue
                break

        self.__line_marks[start:start] = (None for x in xrange(start, end))
        for i in xrange(start, end):
            self.__line_marks[i] = self.create_mark(None, iter, True)
            self.__line_marks[i].line = i
            iter.forward_line()

        for i in xrange(end, len(self.__line_marks)):
            self.__line_marks[i].line += (end - start)

    def on_lines_deleted(self, worksheet, start, end):
        _debug("...lines %d:%d deleted", start, end)
        for i in xrange(start, end):
            self.delete_mark(self.__line_marks[i])

        self.__line_marks[start:end] = []

        for i in xrange(start, len(self.__line_marks)):
            self.__line_marks[i].line -= (end - start)

    def on_chunk_inserted(self, worksheet, chunk):
        _debug("...chunk %s inserted", chunk);
        chunk.pixels_above = chunk.pixels_below = 0
        chunk.results_start_mark = None
        chunk.results_end_mark = None
        chunk.sidebar_results = None
        self.on_chunk_changed(worksheet, chunk, range(0, chunk.end - chunk.start))

    def on_chunk_deleted(self, worksheet, chunk):
        _debug("...chunk %s deleted", chunk);
        self.__delete_results(chunk)

        if chunk.pixels_above != 0:
            self.get_tag_table().remove(chunk.__first_line_tag)
            del chunk.__first_line_tag

        if chunk.pixels_below != 0:
            self.get_tag_table().remove(chunk.__last_line_tag)
            del chunk.__last_line_tag

    def on_chunk_changed(self, worksheet, chunk, changed_lines):
        _debug("...chunk %s changed", chunk);

        if chunk.results_start_mark:
            # Check that the result is still immediately after the chunk, and if
            # not, delete it and insert it again
            iter = self.pos_to_iter(chunk.end - 1)
            if (not _forward_line(iter) or not chunk.results_start_mark in iter.get_marks()):
                self.__delete_results(chunk)
                self.__insert_results(chunk)
        elif not chunk.sidebar_results:
            self.__insert_results(chunk)

        if isinstance(chunk, StatementChunk):
            self.__fontify_statement_chunk(chunk, changed_lines)
        else:
            if isinstance(chunk, CommentChunk):
                tag = self.__comment_tag
            else:
                tag = None
            self.__retag_chunk(chunk, changed_lines, tag)

        self.__adjust_status_tags(chunk)

        # We can't use changed lines to optimize this since pure deletions
        # of lines aren't reflected.

        if chunk.pixels_above != 0:
            self.__reset_first_line_tag(chunk)

        if chunk.pixels_below != 0:
            self.__reset_last_line_tag(chunk)

    def on_chunk_status_changed(self, worksheet, chunk):
        _debug("...chunk %s status changed", chunk)
        self.__adjust_status_tags(chunk)

    def __adjust_status_tags(self, chunk):
        if chunk.results_start_mark is not None:
            start = self.get_iter_at_mark(chunk.results_start_mark)
            end = self.get_iter_at_mark(chunk.results_end_mark)
            if chunk.needs_execute or chunk.needs_compile:
                self.apply_tag(self.__status_tags, start, end)
            elif not chunk.executing:
                self.remove_tag(self.__status_tags, start, end)

        start = self.pos_to_iter(chunk.start)
        end = self.pos_to_iter(chunk.end - 1, -1)
        self.remove_tag(self.__error_line_tag, start, end)

        if isinstance(chunk, StatementChunk) and chunk.error_message and chunk.error_line is not None:
            start = self.pos_to_iter(chunk.start + chunk.error_line - 1)
            end = self.pos_to_iter(chunk.start + chunk.error_line - 1, -1)
            self.apply_tag(self.__error_line_tag, start, end)

    def on_chunk_results_changed(self, worksheet, chunk):
        _debug("...chunk %s results changed", chunk);
        self.__delete_results(chunk)
        self.__insert_results(chunk)

    def on_place_cursor(self, worksheet, line, offset):
        self.place_cursor(self.pos_to_iter(line, offset))

    #######################################################
    # Public API
    #######################################################

    def pos_to_iter(self, line, offset=0):
        """Get an iter at the specification code line and offset

        @param line: the line in the code of the worksheet (not the gtk.TextBuffer line)
        @param offset: the character within the line (defaults 0). -1 means end

        """

        iter = self.get_iter_at_mark(self.__line_marks[line])
        if offset < 0:
            offset = len(self.worksheet.get_line(line))
        iter.set_line_offset(offset)

        return iter

    def iter_to_pos(self, iter, adjust=ADJUST_BEFORE):
        """Get the code line and offset at the given iterator

        Return a tuple of (code_line, offset).

        @param iter: an iterator within the buffer
        @param adjust: how to handle the case where the iterator isn't on a line of code.

              ADJUST_BEFORE: end previous line of code
              ADJUST_AFTER: start of next line of code
              ADJUST_NONE: return (None, None)

        """

        offset = iter.get_line_offset()
        tmp = iter.copy()
        tmp.set_line_offset(0)
        for mark in tmp.get_marks():
            if hasattr(mark, 'line'):
                return (mark.line, offset)

        if adjust == ADJUST_NONE:
            return None, None

        if adjust == ADJUST_AFTER:
            while _forward_line(tmp):
                for mark in tmp.get_marks():
                    if hasattr(mark, 'line'):
                        return mark.line, 0
                # Not found, we must be in a result chunk after the last line
                # fall through to the !after case

        while _backward_line(tmp):
            for mark in tmp.get_marks():
                if hasattr(mark, 'line'):
                    if not tmp.ends_line():
                        tmp.forward_to_line_end()
                    return mark.line, tmp.get_line_offset()

        raise AssertionError("Not reached")

    def get_public_text(self, start=None, end=None):
        """Gets the text in the buffer in the specified range, ignoring results.
        If range only contains results, then return the (text) results.

        This method satisfies the contract required by sanitize_textview_ipc.py

        start - iter for the end of the text  (None == buffer start)
        end - iter for the start of the text (None == buffer end)

        """

        if start is None:
            start = self.get_start_iter();
        if end is None:
            end = self.get_end_iter();

        start_line, start_offset = self.iter_to_pos(start, adjust=ADJUST_AFTER)
        end_line, end_offset = self.iter_to_pos(end, adjust=ADJUST_BEFORE)

        text = self.worksheet.get_text(start_line, start_offset, end_line, end_offset)

        # Coming up with nothing means either the user selected nothing, or the
        # selection was entirely within one result; in the second case, the user
        # wanted the result text.
        if text == "" or text == "\n":
            text = self.get_text(start, end)

        return text

    def get_pair_location(self):
        """Return an iter pointing to the character paired with the character before the cursor, or None"""

        if self.__have_pair:
            return self.get_iter_at_mark(self.__pair_mark)
        else:
            return None

    def in_modification(self):
        """Return True if the text buffer is modifying its contents itself

        This can be useful to distinguish user edits from internal edits.

        """

        return self.__in_modification_count > 0

    def set_pixels_above(self, chunk, pixels_above):
        """Sets the number of pixels of padding above the chunk

        Note that this doesn't work on single-line empty BlankChunk at the end
        of the buffer.

        """

        if pixels_above == chunk.pixels_above:
            return

        if pixels_above != 0:
            if chunk.pixels_above == 0:
                chunk.__first_line_tag = self.create_tag()
                self.__reset_first_line_tag(chunk)
            chunk.__first_line_tag.set_property('pixels-above-lines', pixels_above)
        else:
            self.get_tag_table().remove(chunk.__first_line_tag)
            del chunk.__first_line_tag

        chunk.pixels_above = pixels_above

    def set_pixels_below(self, chunk, pixels_below):
        """Sets the number of pixels of padding below the chunk

        Note that this doesn't work on single-line empty BlankChunk at the end
        of the buffer; things have been set up so that gtk.TextView.set_pixels_below_lines()
        has no effect except for that particular case, allowing this function can
        be combined with gtk.TextView.set_pixels_below_lines() to reliably add
        padding at the end of the buffer.

        """

        if pixels_below == chunk.pixels_below:
            return

        if pixels_below != 0:
            if chunk.pixels_below == 0:
                chunk.__last_line_tag = self.create_tag()
                self.__reset_last_line_tag(chunk)
            chunk.__last_line_tag.set_property('pixels-below-lines', pixels_below)
        else:
            self.get_tag_table().remove(chunk.__last_line_tag)
            del chunk.__last_line_tag

        chunk.pixels_below = pixels_below


######################################################################

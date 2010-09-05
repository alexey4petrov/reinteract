# Copyright 2010 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import gtk
import logging
import os
import pango
import pangocairo

from chunks import StatementChunk, CommentChunk, BlankChunk
from cStringIO import StringIO
import doc_format
from statement import Statement, WarningResult, HelpResult, CustomResult
from style import DEFAULT_STYLE

_debug = logging.getLogger("PrintOperation").debug

# The two phases of printing
_MEASURE = 0
_RENDER = 1

class _Page(object):
    def __init__(self, start_line, end_line):
        self.start_line = start_line
        self.end_line = end_line

class _PageLayout(object):
    # This object  does the actual work of page layout for a worksheet; it keeps
    # of the state of the page layout, including things like the vertical position on the
    # page. During the _MEASURE phase, one _PageLayout object is used for the entire
    # worksheet. During rendering, we create a separate one per page. There's some
    # confusion with pango.Layout in the name; pango.Layout's are used for individual
    # paragraphs of text.

    header_rule_spacing = 0.125 * 72. # 1/8th inch
    header_rule_thickness = 1         # 1pt

    def __init__(self, worksheet, context, phase, page_number=1, page_count=0):
        self.worksheet = worksheet
        self.context = context

        self.font = pango.FontDescription("monospace 12")

        self.phase = phase

        if self.phase == _MEASURE:
            self.pages = []
        else: # phase == _RENDER
            self.cr = self.context.get_cairo_context()

        self.page_number = page_number
        self.page_count = page_count
        self.y = 0
        self.page_start_line = None

    def create_pango_layout(self, text, *styles):
        layout = self.context.create_pango_layout()

        layout.set_text(text)
        layout.set_font_description(self.font)

        # We need to save some stuff for when we render; just stick extra properties on the
        # layout. We may want to move to a setup where we have "print objects" for layouts
        # or custom results.
        layout._left_margin = 0
        layout._right_margin = 0
        layout._paragraph_background = None

        attrs = pango.AttrList()
        for style in styles:
            spec = DEFAULT_STYLE.get_spec(style)
            spec.add_pango_attributes(attrs, start_index=0, end_index=0x7fffffff)

            # We are fudging pixels vs. points here
            if spec.left_margin:
                layout._left_margin = spec.left_margin
            if spec.left_margin:
                layout._right_margin = spec.right_margin
            if spec.paragraph_background:
                layout._paragraph_background = pango.Color(spec.paragraph_background)

        layout._width = self.context.get_width() - layout._left_margin - layout._right_margin
        layout.set_width(int(pango.SCALE * layout._width))

        layout.set_attributes(attrs)

        return layout

    def check_for_page_break(self, height):
        # BlankChunks never force page breaks, otherwise, if we've overflowed, and this
        # chunk isn't already on a page of its own, start a new page
        if (not isinstance(self.current_chunk, BlankChunk) and
            height + self.y > self.context.get_height() and
            self.page_start_line != self.current_chunk.start):
            self.pages.append(_Page(self.page_start_line, self.current_chunk.start))

            self.y = self.y - self.chunk_start_y
            self.chunk_start_y = 0
            self.page_start_line = self.current_chunk.start
            self.page_number += 1
            self.page_count += 1
            self.append_header()

    def append_pango_layout(self, layout):
        _, layout_height = layout.get_size()
        layout_height = layout_height / pango.SCALE

        if self.phase == _MEASURE:
            self.check_for_page_break(layout_height)
        else: # phase == _RENDER
            if layout._paragraph_background is not None:
                self.cr.save()
                self.cr.set_source_rgb(layout._paragraph_background.red / 65535.,
                                       layout._paragraph_background.green / 65535.,
                                       layout._paragraph_background.blue / 65535.)
                self.cr.rectangle(layout._left_margin,
                                  self.y,
                                  layout._width,
                                  layout_height)
                self.cr.fill()
                self.cr.restore()

            self.cr.move_to(layout._left_margin, self.y)
            self.cr.show_layout(layout)

        self.y += layout_height

    def append_header(self):
        if self.worksheet.filename is None:
            filename = "Unsaved Worksheet"
        else:
            filename = os.path.basename(self.worksheet.filename)

        left_layout = self.create_pango_layout(filename, 'header')
        left_width, left_height = left_layout.get_size()
        left_width /= pango.SCALE
        left_height /= pango.SCALE

        right_layout = self.create_pango_layout("Page %d of %d" % (self.page_number, self.page_count))
        right_width, right_height = right_layout.get_size()
        right_width /= pango.SCALE
        right_height /= pango.SCALE

        if self.phase == _RENDER:
            self.cr.move_to(0, self.y)
            self.cr.show_layout(left_layout)

            self.cr.move_to(self.context.get_width() - right_width, self.y)
            self.cr.show_layout(right_layout)

        self.y += max(left_height, right_height)

        self.y += self.header_rule_spacing + self.header_rule_thickness / 2

        if self.phase == _RENDER:
            self.cr.save()
            self.cr.set_line_width(self.header_rule_thickness)
            self.cr.move_to(0, self.y)
            self.cr.line_to(self.context.get_width(), self.y)

            self.cr.stroke()
            self.cr.restore()

        self.y += self.header_rule_spacing + self.header_rule_thickness / 2

    def append_chunk_text(self, chunk):
        text = self.worksheet.get_text(start_line=chunk.start, end_line=chunk.end - 1)

        if isinstance(chunk, CommentChunk):
            layout = self.create_pango_layout(text, 'comment')
        else:
            layout = self.create_pango_layout(text)

        if isinstance(chunk, StatementChunk):
            attrs = layout.get_attributes() # makes a copy
            index = 0

            # The complexity here is because Pango attributes encode positions by byte
            # index for UTF-8 encoded text while we store the tokenization in Unicode
            # character positions.
            for i in xrange(chunk.start, chunk.end):
                line = self.worksheet.get_line(i)
                offset = 0
                for token_type, start_offset, end_offset, _ in chunk.tokenized.get_tokens(i - chunk.start):
                    start_index = index + len(line[offset:start_offset].encode("UTF-8"))
                    end_index = start_index + len(line[start_offset:end_offset].encode("UTF-8"))
                    spec = DEFAULT_STYLE.get_spec(token_type)
                    if spec is not None:
                        spec.add_pango_attributes(attrs, start_index, end_index)
                    index = end_index
                    offset = end_offset
                index += 1 # newline

            layout.set_attributes(attrs) # set the copy back

        self.append_pango_layout(layout)

    def append_chunk_results(self, chunk):
        if not isinstance(chunk, StatementChunk):
            return

        def create_result_layout(text, style=None):
            styles = ['result']
            if style is not None:
                styles.append(style)
            if chunk.needs_execute:
                styles.append('recompute')
            return self.create_pango_layout(text, *styles)

        if chunk.error_message:
            layout = create_result_layout(chunk.error_message)
            self.append_pango_layout(layout)
        elif chunk.results is not None:
            styles = ['result']
            for result in chunk.results:
                if isinstance(result, basestring):
                    layout = create_result_layout(result)
                    self.append_pango_layout(layout)
                elif isinstance(result, WarningResult):
                    layout = create_result_layout(result.message, 'warning')
                    self.append_pango_layout(layout)
                elif isinstance(result, HelpResult):
                    si = StringIO()
                    attrs = pango.AttrList()

                    index = [0] # array so we can mutate within nested function
                    def callback(text, bold):
                        if isinstance(text, unicode):
                            text = text.encode("UTF-8")
                        si.write(text)
                        end_index = index[0] + len(text)
                        if bold:
                            attrs.insert(pango.AttrWeight(pango.WEIGHT_BOLD, index[0], end_index))
                        index[0] = end_index

                    doc_format.format_docs(result.arg, callback)
                    layout = create_result_layout(si.getvalue(), 'help')
                    paragraph_attrs = layout.get_attributes()
                    paragraph_attrs.splice(attrs, 0, index[0])
                    layout.set_attributes(paragraph_attrs)
                    self.append_pango_layout(layout)
                elif isinstance(result, CustomResult):
                    try:
                         if self.phase == _MEASURE:
                             height = result.print_result(self.context, render=False)
                             self.check_for_page_break(height)
                         else:
                             try:
                                 self.cr.save()
                                 self.cr.translate(0, self.y)
                                 height = result.print_result(self.context, render=True)
                             finally:
                                 self.cr.restore()

                         self.y += height
                    except NotImplementedError, e:
                        layout = create_result_layout(unicode(result))
                        self.append_pango_layout(layout)

    def append_chunk(self, chunk):
        if self.page_start_line is None:
            self.append_header()
            self.page_start_line = chunk.start

        self.current_chunk = chunk
        self.chunk_start_y = self.y

        self.append_chunk_text(chunk)
        self.append_chunk_results(chunk)

        self.current_chunk = None
        self.page_end_line = chunk.end

    def finish(self):
        if self.phase == _MEASURE and self.page_start_line is not None:
            self.pages.append(_Page(self.page_start_line, self.page_end_line))

class WorksheetPrintOperation(gtk.PrintOperation):
    """
    Subclass of gtk.PrintOperation to print a worksheet.
    """

    __gsignals__ = {
        'begin-print' : 'override',
        'draw-page': 'override'
    }

    def __init__(self, worksheet):
        gtk.PrintOperation.__init__(self)

        self.worksheet = worksheet

        self.set_unit(gtk.UNIT_POINTS)

    def do_begin_print(self, context):
        page_layout = _PageLayout(self.worksheet, context, phase=_MEASURE)

        for chunk in self.worksheet.iterate_chunks():
            page_layout.append_chunk(chunk)

        page_layout.finish()

        self.__pages = page_layout.pages
        self.set_n_pages(len(self.__pages))

    def do_draw_page(self, context, page_nr):
        page = self.__pages[page_nr]

        page_layout = _PageLayout(self.worksheet, context, phase=_RENDER,
                                  page_number=page_nr + 1, page_count=len(self.__pages))

        for chunk in self.worksheet.iterate_chunks(page.start_line, page.end_line):
           page_layout.append_chunk(chunk)

        page_layout.finish()

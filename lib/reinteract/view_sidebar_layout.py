# Copyright 2011 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import gobject
import gtk

RESIZE_GRIP_WIDTH = 7
RESIZE_DRAW_WIDTH = 1

DEFAULT_SIDEBAR_WIDTH = 440

class ViewSidebarLayout(gtk.VBox):

    """
    Widget that handles laying out a ShellView with a sidebar and associated scrollbars.
    This widget also handles drawing and handling button press events for the draggable
    slider between the view and the sidebar.

    The main reason that we can't do this with stock GTK+ widgets is that we want to
    have the view and the sidebar share a common vertical scrollbar, but have separate
    horizontal scrollbars - this configuration can't be handled with the standard
    gtk.ScrolledWindow.

    Derived from gtk.VBox to reuse logic such as the forall() method that is difficult
    to implement in Python; this derivation should be considered private.

    """

    __gsignals__ = {}

    def __init__(self):
        super(ViewSidebarLayout, self).__init__(self)

        self.view = None
        self.sidebar = None
        self.__vscrollbar = gtk.VScrollbar();
        self.__main_hscrollbar = gtk.HScrollbar();
        self.__sidebar_hscrollbar = gtk.HScrollbar();
        self.sidebar_open = False
        self.__sidebar_width = DEFAULT_SIDEBAR_WIDTH
        self.__in_resize = False

        self.add(self.__vscrollbar)
        self.add(self.__main_hscrollbar)
        self.add(self.__sidebar_hscrollbar)

        self.__main_hscrollbar_changed_id = \
            self.__main_hscrollbar.get_adjustment().connect('changed', self.on_main_hadjustment_changed)
        self.__sidebar_hscrollbar_changed_id = \
            self.__sidebar_hscrollbar.get_adjustment().connect('changed', self.on_sidebar_hadjustment_changed)
        self.__vscrollbar_changed_id = \
            self.__vscrollbar.get_adjustment().connect('changed', self.on_vadjustment_changed)

        self.__main_hscrollbar_visible = False
        self.__sidebar_hscrollbar_visible = True
        self.__vscrollbar_visible = True
        self.__resize_window = None

        self.set_redraw_on_allocate(True)

        self.connect('destroy', self.on_destroy)

    #######################################################
    # Utility
    #######################################################

    def __get_resize_rect(self):
        result = self.allocation
        if self.view:
            result.x += self.view.allocation.width - (RESIZE_GRIP_WIDTH - RESIZE_DRAW_WIDTH) / 2
        result.width = RESIZE_GRIP_WIDTH
        if self.__main_hscrollbar_visible or self.__sidebar_hscrollbar_visible:
            _, sh = self.__main_hscrollbar.size_request()
            result.height -= sh

        return result

    #######################################################
    # Callbacks
    #######################################################

    def on_main_hadjustment_changed(self, adjustment):
        visible = adjustment.upper - adjustment.lower > adjustment.page_size
        if visible != self.__main_hscrollbar_visible:
            self.__main_hscrollbar_visible = visible
            self.queue_resize()

    def on_sidebar_hadjustment_changed(self, adjustment):
        visible = adjustment.upper - adjustment.lower > adjustment.page_size
        if visible != self.__sidebar_hscrollbar_visible:
            self.__sidebar_hscrollbar_visible = visible
            self.queue_resize()

    def on_vadjustment_changed(self, adjustment):
        visible = adjustment.upper - adjustment.lower > adjustment.page_size
        if visible != self.__vscrollbar_visible:
            self.__vscrollbar_visible = visible
            self.queue_resize()

    #######################################################
    # Overrides
    #######################################################

    def on_destroy(self, widget):
        self.__main_hscrollbar.get_adjustment().disconnect(self.__main_hscrollbar_changed_id)
        self.__sidebar_hscrollbar.get_adjustment().disconnect(self.__sidebar_hscrollbar_changed_id)
        self.__vscrollbar.get_adjustment().disconnect(self.__vscrollbar_changed_id)

    def do_map(self):
        gtk.VBox.do_map(self)

        if self.sidebar_open:
            self.__resize_window.show()

    def do_unmap(self):
        gtk.VBox.do_unmap(self)
        self.__resize_window.hide()

    def do_realize(self):
        gtk.VBox.do_realize(self)

        resize_rect = self.__get_resize_rect()
        self.__resize_window = gtk.gdk.Window(self.get_parent_window(),
                                              resize_rect.width, resize_rect.height,
                                              gtk.gdk.WINDOW_CHILD,
                                              (gtk.gdk.SCROLL_MASK |
                                               gtk.gdk.BUTTON_PRESS_MASK |
                                               gtk.gdk.BUTTON_RELEASE_MASK |
                                               gtk.gdk.POINTER_MOTION_MASK |
                                               gtk.gdk.POINTER_MOTION_HINT_MASK),
                                              gtk.gdk.INPUT_ONLY,
                                              x=resize_rect.x, y=resize_rect.y)
        self.__resize_window.set_cursor(gtk.gdk.Cursor(gtk.gdk.SB_H_DOUBLE_ARROW))
        self.__resize_window.set_user_data(self)

    def do_unrealize(self):
        self.__resize_window.set_user_data(None)
        gtk.VBox.do_unrealize(self)

    def do_size_request(self, requisition):
        vsw, vsh = self.__vscrollbar.size_request()
        mhsw, mhsh = self.__main_hscrollbar.size_request()

        shsw, shsh = self.__sidebar_hscrollbar.size_request()
        if self.view:
            self.view.size_request()
        if self.sidebar:
            sw, sh = self.sidebar.size_request()
        else:
            sw, sh = 0, 0

        if self.sidebar_open:
            requisition.width = vsw + mhsw + max(sw, shsw)
            requisition.height = vsh + max(mhsh, shsh)
        else:
            requisition.width = vsw + mhsw
            requisition.height = vsh + mhsh

    def do_size_allocate(self, allocation):
        self.allocation = allocation

        mhsw, mhsh = self.__main_hscrollbar.size_request()
        shsw, shsh = self.__sidebar_hscrollbar.size_request()
        vsw, vsh = self.__vscrollbar.size_request()

        child_allocation = gtk.gdk.Rectangle()

        # This is more-or-less the same logic that GtkScrolledWindow for automatic
        # scrollbars - we start with the current scrollbars, allocate the view
        # with the resulting allocation, see if the scrollbars are still needed
        # and repeat until the scrollbars stop changing.
        #
        # This approach does mean that there is hysteresis - we can have scrollbars
        # in a case where if we removed the scrollbars we'd have enough space
        # that they aren't needed. But with the way that the way that the GTK+
        # scrollable protocol works, starting from scratch each time would result
        # in unnecessary window resizes.

        first = True
        while True:
            prev_vscrollbar_visible = self.__vscrollbar_visible
            prev_hscrollbar_visible = self.__main_hscrollbar_visible

            if self.sidebar_open:
                sidebar_width = max(self.__sidebar_width, shsw) + RESIZE_DRAW_WIDTH
            else:
                sidebar_width = 0

            available_width = allocation.width - sidebar_width
            available_height = allocation.height
            if self.__vscrollbar_visible:
                available_width -= vsw
            if self.__main_hscrollbar_visible or (self.sidebar_open and self.__sidebar_hscrollbar_visible):
                available_height -= mhsh

            if self.sidebar_open and available_width < mhsw:
                sidebar_width -= mhsw - available_width
                available_width = mhsw

            child_allocation.x = allocation.x
            child_allocation.width = available_width
            child_allocation.y = allocation.y
            child_allocation.height = available_height
            if self.view:
                self.view.size_allocate(child_allocation)

            if (not first and
                self.__vscrollbar_visible != prev_vscrollbar_visible and
                self.__main_hscrollbar_visible != prev_hscrollbar_visible):

                # A loop switching between a vertical and horizontal scrollbar, we
                # need them both. At this point, the GtkScrolledWindow code bails
                # out and returns, but I'm not sure why - I don't think this will
                # actually ever occur with the fairly straightforward relayout
                # behavior of ShellView

                self.__vscrollbar_visible = True
                self.__main_hscrollbar_visible = True
            else:
                if (self.__vscrollbar_visible == prev_vscrollbar_visible and
                    self.__main_hscrollbar_visible == prev_hscrollbar_visible):
                    break

            first = False

        # Once we've determined the allocation of the main view, allocate the
        # remaining children.

        child_allocation.x = allocation.x
        child_allocation.width = available_width
        child_allocation.y = allocation.y + available_height
        child_allocation.height = mhsh
        self.__main_hscrollbar.set_child_visible(self.__main_hscrollbar_visible)
        self.__main_hscrollbar.size_allocate(child_allocation)

        if self.sidebar:
            child_allocation.x = allocation.x + available_width + RESIZE_DRAW_WIDTH
            child_allocation.width = max(sidebar_width - RESIZE_DRAW_WIDTH, 1)
            child_allocation.y = allocation.y
            child_allocation.height = available_height
            self.sidebar.set_child_visible(self.sidebar_open)
            self.sidebar.size_allocate(child_allocation)

        child_allocation.x = allocation.x + available_width + RESIZE_DRAW_WIDTH
        child_allocation.width = max(sidebar_width - RESIZE_DRAW_WIDTH, 1)
        child_allocation.y = allocation.y + available_height
        child_allocation.height = shsh
        self.__sidebar_hscrollbar.set_child_visible(self.sidebar_open and self.__sidebar_hscrollbar_visible)
        self.__sidebar_hscrollbar.size_allocate(child_allocation)

        child_allocation.x = allocation.x + available_width + sidebar_width
        child_allocation.width = vsw
        child_allocation.y = allocation.y
        child_allocation.height = available_height
        self.__vscrollbar.set_child_visible(self.__vscrollbar_visible)
        self.__vscrollbar.size_allocate(child_allocation)

        if self.__resize_window:
            resize_rect = self.__get_resize_rect()
            self.__resize_window.move_resize(resize_rect.x, resize_rect.y,
                                             resize_rect.width, resize_rect.height)
            self.__resize_window.raise_()

    def do_expose_event(self, event):
        resize_rect = self.__get_resize_rect()
        resize_rect.x += (RESIZE_GRIP_WIDTH - RESIZE_DRAW_WIDTH) / 2
        resize_rect.width = RESIZE_DRAW_WIDTH

        cr = event.window.cairo_create()

        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.rectangle(resize_rect.x, resize_rect.y, resize_rect.width, resize_rect.height)
        cr.fill()

        allocation = self.allocation
        cr.set_source_color(self.style.bg[self.state])
        cr.rectangle(resize_rect.x, resize_rect.y + resize_rect.height,
                     allocation.x + allocation.width - resize_rect.x,
                     allocation.y + allocation.height - (resize_rect.y + resize_rect.height))
        cr.fill()

        return gtk.VBox.do_expose_event(self, event)

    def do_button_press_event(self, event):
        if event.button == 1:
            self.__in_resize = True
            self.__resize_start_width = self.__sidebar_width
            self.__resize_start_x = event.x_root
            return True

        return False

    def do_button_release_event(self, event):
        if event.button == 1 and self.__in_resize:
            self.do_motion_notify_event(event)
            self.__in_resize = False
            return True

        return False

    def do_motion_notify_event(self, event):
        if self.__in_resize:
            # The effective sidebar width is also constrained in the allocation
            # process - we constrain it here so that the internall saved size doesn't
            # get set to anything too funky.

            width = self.__resize_start_width +  self.__resize_start_x - event.x_root
            width = max(width, 1)

            max_width = self.allocation.width - RESIZE_DRAW_WIDTH - 1
            if self.__vscrollbar_visible:
                vsw, _ = self.__vscrollbar.size_request()
                max_width -= vsw
            width = min(width, max_width)

            self.sidebar_width = width

        return False

    def do_scroll_event(self, event):
        if event.direction == gtk.gdk.SCROLL_UP or event.direction == gtk.gdk.SCROLL_DOWN:
            scrollbar = self.__vscrollbar;
        else:
            window = event.window
            scrollbar = None
            while window and not scrollbar:
                widget = window.get_user_data()
                if widget == self:
                    break
                elif widget == self.view or widget == self.__main_hscrollbar:
                    scrollbar = self.__main_hscrollbar
                elif widget == self.sidebar or widget == self.__sidebar_hscrollbar:
                    scrollbar = self.__sidebar_hscrollbar

                window = window.get_parent()

        if scrollbar and scrollbar.get_child_visible():
            # Logic from _gtk_range_get_wheel_delta()
            adjustment = scrollbar.get_adjustment()
            delta = adjustment.page_size ** (2.0 / 3.0)

            if event.direction == gtk.gdk.SCROLL_UP or event.direction == gtk.gdk.SCROLL_LEFT:
                delta = -delta

            value = adjustment.value + delta
            value = max(value, adjustment.lower)
            value = min(value, adjustment.upper - adjustment.page_size)
            adjustment.set_value(value)

    #######################################################
    # Public API
    #######################################################

    def set_view(self, view):
        if self.view:
            self.view.set_scroll_adjustments(None, None)
            self.remove(view)

        self.view = view

        if view:
            self.add(view)
            view.set_scroll_adjustments(self.__main_hscrollbar.get_adjustment(),
                                        self.__vscrollbar.get_adjustment())

    def set_sidebar(self, sidebar):
        if self.sidebar:
            self.sidebar.set_scroll_adjustments(None, None)
            self.remove(self.sidebar)

        self.sidebar = sidebar

        if sidebar:
            self.add(sidebar)
            sidebar.set_scroll_adjustments(self.__sidebar_hscrollbar.get_adjustment(),
                                           self.__vscrollbar.get_adjustment())

    def set_sidebar_open(self, open_):
        self.sidebar_open = open_
        self.queue_resize()

        if self.__resize_window:
            if self.sidebar_open:
                self.__resize_window.show()
            else:
                self.__resize_window.hide()

    def __get_sidebar_width(self):
        return self.__sidebar_width

    def __set_sidebar_width(self, sidebar_width):
        self.__sidebar_width = sidebar_width
        self.queue_resize()

    sidebar_width = gobject.property(getter=__get_sidebar_width,
                                     setter=__set_sidebar_width,
                                     type=int, default=DEFAULT_SIDEBAR_WIDTH)

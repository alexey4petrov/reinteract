# Copyright 2011 Owen Taylor
#
# This file is part of Reinteract and distributed under the terms
# of the BSD license. See the file COPYING in the Reinteract
# distribution for full details.
#
########################################################################

import gtk

LEFT_MARGIN = 5

class Sidebar(gtk.VBox):

    """
    Widget that holds result widgets with display='side'. Each such result widget
    is contained within a SidebarSlot, which corresponds to the chunk that
    generated the result widget as output.

    This widget has independent horizontal scrolling, and updates the horizontal
    adjustment based on the content width, but the vertical scrolling is purely
    slaved to the view.

    Each child widget has its own gtk.gdk.Window() so that we can move them
    around at a visual level without reallocating the children - builtin GTK+
    widgets do this without the intermediate window by poking new values
    into the child's allocations after scrolling, but we can't do that here.

    Derived from gtk.VBox to reuse logic such as the forall() method that is difficult
    to implement in Python; this derivation should be considered private.

    """

    __gsignals__ = {}

    def __init__(self):
        super(Sidebar, self).__init__(self)
        self.hadjustment = None
        self.vadjustment = None

        self.x_offset = 0
        self.y_offset = 0

        self.slots = []

        self.__freeze_positions_count = 0

        self.unset_flags(gtk.NO_WINDOW)

        self.connect('destroy', self.on_destroy)

    #######################################################
    # Utility
    #######################################################

    def __iterate_children(self):
        for slot in self.slots:
            for child in slot.children:
                yield child

    def _layout_children(self):
        # This function takes care of updating the vertical position of children,
        # both when slot positions change and when we scroll vertically.
        # (We try to keep widgets onscreen when possible, so a vertical scroll
        # doesn't do a pure scroll on the children.)

        if self.__freeze_positions_count > 0:
            return

        allocation = self.allocation

        # We first compute where each child should go

        last_y = None
        for slot in self.slots:
            y = slot.top - self.y_offset
            results_height = slot.get_results_height()

            # If the results are larger than the slot, we just position them at the
            # top of the slop.
            #
            # If the results are smaller than the slot and we can make more of the
            # results visible by moving the results down, we do so

            if y < 0 and slot.height > results_height:
                # Slot         |------------------|
                # Screen            0----------A
                # Results        |-------------|

                # Slot         |------------------|
                # Screen                       0--A-------|
                # Results           |-------------|

                # Slot         |------------------|
                # Screen            0----------A
                # Results           |----|

                # Slot         |------------------|
                # Screen                       0--A-------|
                # Results                    |----|

                onscreen_slot_end = min(slot.top + slot.height - self.y_offset, allocation.height) # (A)
                y = min(0, onscreen_slot_end - results_height)

            for child in slot.children:
                child.target_y = y
                _, h = child.widget.size_request()
                y += h

            last_y = y

        # Now positin the children - we want to use gtk.gdk.Window.scroll()
        # when possible, since that will produce the smoothest, more efficient
        # redraw. Figure out what the most common vertical movement amount is,
        # scroll by that, and then fix up the rest.

        deltas = {}
        max_count = 0
        max_delta = None

        for child in self.__iterate_children():
            delta = child.target_y - child.y
            if delta in deltas:
                deltas[delta] += 1
            else:
                deltas[delta] = 1

            if deltas[delta] > max_count:
                max_count = deltas[delta]
                max_delta = delta

        if self.window:
            if max_count > 0 and max_delta != 0:
                self.window.scroll(0, max_delta)
                for child in self.__iterate_children():
                    child.y += max_delta

        for child in self.__iterate_children():
            if child.y != child.target_y:
                child.y = child.target_y
                child.resize_window()

    #######################################################
    # Callbacks
    #######################################################

    def on_hadjustment_value_changed(self, adjustment):
        value = int(adjustment.value)

        if value != self.x_offset:
            if self.window:
                self.window.scroll(self.x_offset - value, 0)

            self.x_offset = value

    def on_vadjustment_value_changed(self, adjustment):
        value = int(adjustment.value)

        if value != self.y_offset:
            self.y_offset = value
            self._layout_children()

    #######################################################
    # Overrides
    #######################################################

    def on_destroy(self, widget):
        self.set_scroll_adjustments(None, None)

    def do_map(self):
        gtk.VBox.do_map(self)
        for child in self.__iterate_children():
            child.window.show()

    def do_realize(self):
        self.set_flags(gtk.REALIZED)
        allocation = self.allocation
        window = gtk.gdk.Window(self.get_parent_window(),
                                allocation.width, allocation.height,
                                gtk.gdk.WINDOW_CHILD,
                                (gtk.gdk.EXPOSURE_MASK |
                                 gtk.gdk.SCROLL_MASK |
                                 gtk.gdk.BUTTON_PRESS_MASK |
                                 gtk.gdk.BUTTON_RELEASE_MASK |
                                 gtk.gdk.POINTER_MOTION_MASK |
                                 gtk.gdk.POINTER_MOTION_HINT_MASK),
                                gtk.gdk.INPUT_OUTPUT,
                                x=allocation.x, y=allocation.y)
        window.set_user_data(self)
        window.set_background(self.style.white)
        self.set_style(self.style.attach(window))
        self.set_window(window)

        for child in self.__iterate_children():
            child.create_window()

    def do_unrealize(self):
        for child in self.__iterate_children():
            child.destroy_window()

        gtk.VBox.do_unrealize(self)

    def do_size_allocate(self, allocation):
        self._layout_children()

        self.allocation = allocation
        if self.window:
            self.window.move_resize(allocation.x, allocation.y,
                                    allocation.width, allocation.height)

        if self.hadjustment:
            self.hadjustment.page_increment = 0.9 * allocation.width
            self.hadjustment.page_size = allocation.width

        child_allocation = gtk.gdk.Rectangle()

        for child in self.__iterate_children():
            w, h = child.widget.size_request()
            child_allocation.x = 0
            child_allocation.y = 0
            child_allocation.width = w
            child_allocation.height = h
            child.widget.size_allocate(child_allocation)
            child.resize_window()

    def do_size_request(self, requisition):
        content_width = 0
        for child in self.__iterate_children():
            w, h = child.widget.size_request()
            content_width = max(content_width, w)

        if self.hadjustment:
            self.hadjustment.upper = content_width

        requisition.width = 1
        requisition.height = 1

    def do_expose_event(self, event):
        for child in self.__iterate_children():
            self.propagate_expose(child.widget, event)

    #######################################################
    # Public API
    #######################################################

    def set_scroll_adjustments(self, hadjustment, vadjustment):
        if self.hadjustment:
            self.hadjustment.disconnect(self.__hadjustment_value_changed_id)
        if self.vadjustment:
            self.vadjustment.disconnect(self.__vadjustment_value_changed_id)

        self.hadjustment = hadjustment
        self.vadjustment = vadjustment

        if self.hadjustment:
            # value/lower/upper/step_increment/page_increment/page_size
            self.hadjustment.configure(0, # value
                                       0, self.requisition.width, # lower, upper
                                       10, 0.9 * self.allocation.width, # step_increment, page_increment
                                       self.allocation.width) # page_size
            self.__hadjustment_value_changed_id = self.hadjustment.connect('value-changed', self.on_hadjustment_value_changed)
            self.on_hadjustment_value_changed(self.hadjustment)

        if self.vadjustment:
            self.__vadjustment_value_changed_id = self.vadjustment.connect('value-changed', self.on_vadjustment_value_changed)
            self.on_vadjustment_value_changed(self.vadjustment)

    def add_slot(self, chunk, widgets):
        children = []
        for widget in widgets:
            child = SidebarChild(self, widget)
            if self.window:
                child.create_window()
            self.add(child.widget)
            children.append(child)

        slot = SidebarSlot(self, chunk, children)
        self.slots.append(slot)
        self.slots.sort(key=lambda child: child.chunk.start)

    def remove_slot(self, chunk):
        for i, slot in enumerate(self.slots):
            if slot.chunk == chunk:
                for child in slot.children:
                    self.remove(child.widget)
                    if self.window:
                        child.destroy_window()
                del self.slots[i]
                return

    def scroll_to_slot_results(self, slot):
        page_height = self.vadjustment.page_size
        page_top = int(self.vadjustment.value)

        # We want to scroll a minimum distance, so as much as possible of the
        # results are visible.
        results_top = slot.children[0].y + self.y_offset
        results_height = slot.get_results_height()

        if page_height < results_height:
            # Scroll so the result occupies the full screen
            if page_top < results_top:
                page_top = results_top
            elif page_top + page_height > results_top + results_height:
                page_top = results_top + top.height - page_height
        else:
            # Scroll so the result is fully onscreen
            if results_top < page_top:
                page_top = results_top
            elif results_top + results_height > page_top + page_height:
                page_top = results_top + results_height - page_height

        self.vadjustment.set_value(page_top)

    def freeze_positions(self):
        self.__freeze_positions_count += 1

    def thaw_positions(self):
        self.__freeze_positions_count -= 1
        if self.__freeze_positions_count == 0:
            self._layout_children()

###########################################################

class SidebarChild(object):
    def __init__(self, sidebar, widget):
        self.sidebar = sidebar
        self.widget = widget
        self.window = None
        self.y = 0
        self.target_y = 0

    def create_window(self):
        allocation = self.widget.allocation
        self.window = gtk.gdk.Window(self.sidebar.window,
                                     allocation.width, allocation.height,
                                     gtk.gdk.WINDOW_CHILD,
                                     (gtk.gdk.EXPOSURE_MASK |
                                      gtk.gdk.SCROLL_MASK |
                                      gtk.gdk.BUTTON_PRESS_MASK |
                                      gtk.gdk.BUTTON_RELEASE_MASK |
                                      gtk.gdk.POINTER_MOTION_MASK |
                                      gtk.gdk.POINTER_MOTION_HINT_MASK),
                                     gtk.gdk.INPUT_OUTPUT,
                                     x=LEFT_MARGIN, y=self.y)
        self.window.set_background(self.sidebar.style.white)
        self.window.set_user_data(self.sidebar)
        self.widget.set_parent_window(self.window)

        if self.sidebar.get_mapped():
            self.window.show()

    def destroy_window(self):
        self.window.set_user_data(None)
        self.window.destroy()
        self.window = None

    def resize_window(self):
        if self.window:
            allocation = self.widget.allocation
            self.window.move_resize(LEFT_MARGIN - self.sidebar.x_offset, self.y,
                                    allocation.width, allocation.height)

class SidebarSlot(object):
    def __init__(self, sidebar, chunk, children):
        self.sidebar = sidebar
        self.chunk = chunk
        self.children = children
        self.top = -1
        self.height = 0

    def set_position(self, top, height):
        if self.top == top and self.height == height:
            return

        self.top = top
        self.height = height
        self.sidebar._layout_children()

    def get_results_height(self):
        result = 0
        for child in self.children:
            _, h = child.widget.size_request()
            result += h

        return result


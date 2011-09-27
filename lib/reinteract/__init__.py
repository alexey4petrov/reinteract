import gobject

#  https://bugzilla.gnome.org/show_bug.cgi?id=644039
def fixed_default_setter(self, instance, value):
    setattr(instance, '_property_helper_'+self.name, value)

def fixed_default_getter(self, instance):
    return getattr(instance, '_property_helper_'+self.name, self.default)

def monkey_patch_gobject_property():
    p = gobject.property()
    if hasattr(p, '_values'):
        gobject.propertyhelper.property._default_setter = fixed_default_setter
        gobject.propertyhelper.property._default_getter = fixed_default_getter

monkey_patch_gobject_property()

/* -*- mode: ObjC; c-basic-offset: 4; indent-tabs-mode: nil; -*- */
#include "ThunkPython.h"

#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <stdarg.h>

#import "MenuController.h"
#import "pyNativeMainMenu.h"

static void
die(const char *format, ...)
{
    if (PyErr_Occurred())
        PyErr_Print();

    va_list vap;
    va_start(vap, format);
    vfprintf(stderr, format, vap);
    va_end(vap);

    fprintf(stderr, "\n");

    exit(1);
}

static PyObject *
getModuleAttribute(const char *moduleName, const char *attributeName)
{
    PyObject *module = PyImport_ImportModule(moduleName);
    if (module == NULL)
        die("Cannot import %s module", moduleName);

    PyObject *attribute = PyObject_GetAttrString(module, attributeName);
    if (attribute == NULL)
        die("Cannot get %s.%s", moduleName, attributeName);

    Py_DECREF(module);

    return attribute;
}

static BOOL
dirExists(NSString *path)
{
    struct stat s;

    if (stat([path UTF8String], &s) != 0)
        return FALSE;

    return S_ISDIR(s.st_mode);
}

int main(int argc, char *argv[])
{
    NSAutoreleasePool *pool = [[NSAutoreleasePool alloc] init];

    NSBundle *mainBundle = [NSBundle mainBundle];
    NSString *resourcePath = [mainBundle resourcePath];

    /* This allocates the shared NSApplication object and stores it in the
     * NSApp global variable */
    [NSApplication sharedApplication];

    /* Find the right version of Python and fill the vtable of "thunks"
     * to that library */
    if (!init_thunk_python())
        exit(1);

    /* Normal Python initializatin */
    Py_Initialize();
    PySys_SetArgv(argc, (char **)argv);

    /* Set up sys.path and locate special directories. We do this in Python
     * on other platforms; conceptually program this replaces Reinteract.py
     * and so has that responsibility */
    PyObject *sysPath = getModuleAttribute("sys", "path");

    NSString *dialogsDir;
    NSString *examplesDir;

    /* If we are being run from the full bundle, then our Python files, etc.
     * are inside the Resources directory of the bundle. If we running from
     * the shell bundle we create uninstalled, then we expect to find stuff
     * up one directory from the to of the bundle.
     */
    NSString *pythonDir = [resourcePath stringByAppendingPathComponent:@"python"];
    if (dirExists(pythonDir)) {
        dialogsDir = [resourcePath stringByAppendingPathComponent:@"dialogs"];
        examplesDir = [resourcePath stringByAppendingPathComponent:@"examples"];

        NSString *externalDir = [resourcePath stringByAppendingPathComponent:@"external"];
        PyObject *toInsert = Py_BuildValue("(ss)", [pythonDir UTF8String], [externalDir UTF8String]);
        PySequence_SetSlice(sysPath, 0, 0, toInsert);
        Py_DECREF(toInsert);
    } else {
        NSString *baseDir = [[mainBundle bundlePath] stringByDeletingLastPathComponent];
        dialogsDir = [baseDir stringByAppendingPathComponent:@"dialogs"];
        examplesDir = [baseDir stringByAppendingPathComponent:@"examples"];

        pythonDir = [baseDir stringByAppendingPathComponent:@"lib"];

        PyObject *toInsert = Py_BuildValue("(s)", [pythonDir UTF8String]);
        PySequence_SetSlice(sysPath, 0, 0, toInsert);
        Py_DECREF(toInsert);
    }

    /* Set attributes in the global_settings objects */

    PyObject *globalSettings = getModuleAttribute("reinteract.global_settings", "global_settings");

    PyObject *pyDialogsDir = PyString_FromString([dialogsDir UTF8String]);
    PyObject_SetAttrString(globalSettings, "dialogs_dir", pyDialogsDir);
    Py_DECREF(pyDialogsDir);

    PyObject *pyExamplesDir = PyString_FromString([examplesDir UTF8String]);
    PyObject_SetAttrString(globalSettings, "examples_dir", pyExamplesDir);
    Py_DECREF(pyExamplesDir);

    PyObject_SetAttrString(globalSettings, "main_menu_mode", Py_True);

    /* Initialize reinteract.NativeMainMenu module; this provides two-way
     * communication between Python and the menu */
    init_py_native_main_menu();

    /* We're all set, now run run reinteract.main.main() */

    PyObject *main_module = getModuleAttribute("reinteract.main", "main");
    PyObject *result = PyObject_CallFunction(main_module, "");
    if (result  == NULL)
        die("Error calling main() function");

    Py_DECREF(result);

    Py_Finalize();

    [pool drain];

    return 0;
}
/* -*- mode: C; c-basic-offset: 4; indent-tabs-mode: nil; -*-
 *
 * Copyright 2008 Owen Taylor
 *
 * This file is part of Reinteract and distributed under the terms
 * of the BSD license. See the file COPYING in the Reinteract
 * distribution for full details.
 *
 ************************************************************************/

/* See comment in ThunkPython.h for what this is about */

#include <config.h>
#include <dlfcn.h>
#include <stdlib.h>

#include "ThunkPython.h"

#define concat(x,y) x#y

#define LOOKUP_SYMBOL(s)                                        \
    do {                                                        \
        python_thunks.thunk_##s = dlsym(handle, #s);            \
        if (python_thunks.thunk_##s == NULL) {                  \
            fprintf(stderr, "Cannot find symbol %s\n", #s);     \
            return 0;                                           \
        }                                                       \
    }                                                           \
    while (0)

static int
file_exists(const char *path)
{
    struct stat s;

    if (stat(path, &s) != 0)
        return 0;

    return 1;
}

typedef struct {
    int major;
    int minor;
    int micro;
} Version;

static int
parse_version(const char *version_str,
              Version    *version)
{
    const char *dot1;
    const char *dot2;

    version->major = atoi(version_str);

    dot1 = version_str;
    while (isdigit(*dot1))
        dot1++;

    if (*dot1 != '.')
        return 0;

    version->minor = atoi(dot1 + 1);

    dot2 = dot1 + 1;
    while (isdigit(*dot2))
        dot2++;

    if (*dot2 != '.')
        version->micro = 0;
    else
        version->micro = atoi(dot2 + 1);

    return 1;
}

static int
good_version(const char *version_str)
{
    Version version, required;

    if (!parse_version(version_str, &version) ||
        !parse_version(MIN_PYTHON_VERSION, &required))
        return 0;

    if (version.major != required.major)
        return 0;
    if (version.minor > required.minor)
        return 1;
    if (version.minor < required.minor)
        return 0;
    return version.micro >= required.micro;
}

static void *
dlopen_framework_version(const char *framework_dir,
                         const char *version)
{
    char *buf;
    const char *(*py_get_version) (void);

    if (version != NULL) {
        buf = malloc(strlen(framework_dir) + 1 + strlen("Versions") + 1 + strlen(version) + 1 + strlen("Python") + 1);
        if (!buf)
            return NULL;

        strcpy(buf, framework_dir);
        strcat(buf, "/");
        strcat(buf, "Versions");
        strcat(buf, "/");
        strcat(buf, version);
        strcat(buf, "/");
        strcat(buf, "Python");
    } else {
        buf = malloc(strlen(framework_dir) + 1 + strlen("Python") + 1);
        if (!buf)
            return NULL;

        strcpy(buf, framework_dir);
        strcat(buf, "/");
        strcat(buf, "Python");
    }

    /* This is to prevent some magic behavior in dlopen where dlopening a
     * non-existing version inside a framework will open a system-installed
     * copy of that version instead: not what we want with PYTHON_FRAMEWORK_DIR
     */
    if (!file_exists(buf))
        return NULL;

    void *handle = dlopen(buf, RTLD_GLOBAL | RTLD_LAZY);
    free(buf);

    py_get_version = dlsym(handle, "Py_GetVersion");
    if (!py_get_version) {
        fprintf(stderr, "Can't lookup up Py_GetVersion in library");
        dlclose(handle);
        return NULL;
    }

    if (!good_version(py_get_version())) {
        dlclose(handle);
        return NULL;
    }

    return handle;
}

static void *
dlopen_framework(const char *framework_dir)
{
    void *handle;

    if (strstr(framework_dir, "Versions/") != NULL) {
        handle = dlopen_framework_version(framework_dir, NULL);
    } else {
        handle = dlopen_framework_version(framework_dir, "2.7");
        if (!handle)
            handle = dlopen_framework_version(framework_dir, "2.6");
    }

    return handle;
}

int
init_thunk_python(const char *framework_dir)
{
    void *handle = NULL;

    if (framework_dir) {
        handle = dlopen_framework(framework_dir);
    } else {
        if (!handle)
            handle = dlopen_framework("/Library/Frameworks/Python.framework");

        if (!handle)
            handle = dlopen_framework("/System/Library/Frameworks/Python.framework");
    }

    if (!handle) {
        fprintf(stderr, "Cannot find path to Python framework\n");
        return 0;
    }

    LOOKUP_SYMBOL(PyArg_ParseTuple);
    LOOKUP_SYMBOL(PyErr_Occurred);
    LOOKUP_SYMBOL(PyErr_Occurred);
    LOOKUP_SYMBOL(PyErr_Print);
    LOOKUP_SYMBOL(PyErr_SetString);
    LOOKUP_SYMBOL(PyGILState_Ensure);
    LOOKUP_SYMBOL(PyGILState_Release);
    LOOKUP_SYMBOL(PyImport_ImportModule);
    LOOKUP_SYMBOL(PyList_New);
    LOOKUP_SYMBOL(PyList_SetItem);
    LOOKUP_SYMBOL(PyModule_AddObject);
    LOOKUP_SYMBOL(PyObject_CallFunction);
    LOOKUP_SYMBOL(PyObject_CallMethod);
    LOOKUP_SYMBOL(PyObject_GetAttrString);
    LOOKUP_SYMBOL(PyObject_SetAttrString);
    LOOKUP_SYMBOL(PySequence_SetSlice);
    LOOKUP_SYMBOL(PyString_FromString);
    LOOKUP_SYMBOL(PySys_SetArgv);
    LOOKUP_SYMBOL(PyType_GenericNew);
    LOOKUP_SYMBOL(PyType_IsSubtype);
    LOOKUP_SYMBOL(PyType_Ready);
    LOOKUP_SYMBOL(PyUnicodeUCS2_FromUnicode);
    LOOKUP_SYMBOL(Py_BuildValue);
    LOOKUP_SYMBOL(Py_InitModule4);
    LOOKUP_SYMBOL(Py_Initialize);
    LOOKUP_SYMBOL(Py_Finalize);
    LOOKUP_SYMBOL(_Py_NoneStruct);
    LOOKUP_SYMBOL(_Py_TrueStruct);
    LOOKUP_SYMBOL(_Py_ZeroStruct);
    LOOKUP_SYMBOL(PyExc_RuntimeError);
    LOOKUP_SYMBOL(PyExc_TypeError);

    return 1;
}

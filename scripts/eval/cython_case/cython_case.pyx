# distutils: language = c++

from __future__ import annotations

from libcpp.vector cimport vector
from libc.stdint cimport uint8_t
from libc.stddef cimport size_t
from libc.string cimport memcpy
from cpython.buffer cimport PyObject_GetBuffer, PyBuffer_Release, PyBUF_SIMPLE, Py_buffer


# This intentionally relies on Cython's default conversion semantics for C++ STL vectors.
# It is meant as a binding-layer case study: what conversion policy does the layer pick
# when given a Python object that can be interpreted as both a buffer and a sequence?
def vec_len(vector[uint8_t] v):
    return v.size()


# A contiguous-copy baseline using the buffer protocol (explicit, memcpy-like).
def buffer_copy_len(obj):
    cdef Py_buffer view
    cdef Py_ssize_t n
    cdef vector[uint8_t] v
    if PyObject_GetBuffer(obj, &view, PyBUF_SIMPLE) != 0:
        raise TypeError("object does not export a contiguous buffer (PyBUF_SIMPLE)")
    try:
        n = view.len
        if n > 0:
            v.resize(<size_t>n)
            memcpy(<void*>&v[0], view.buf, <size_t>n)
        return v.size()
    finally:
        PyBuffer_Release(&view)

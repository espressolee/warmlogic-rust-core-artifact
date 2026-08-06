#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cstdint>
#include <cstring>
#include <vector>

namespace py = pybind11;

size_t vec_len(std::vector<uint8_t> v) {
    return v.size();
}

size_t buffer_copy_len(py::buffer b) {
    auto info = b.request();
    if (info.ndim != 1) {
        throw py::type_error("expected 1D buffer");
    }
    if (info.itemsize != 1) {
        throw py::type_error("expected itemsize == 1");
    }
    if (info.strides.empty() || info.strides[0] != 1) {
        throw py::type_error("expected C-contiguous (stride == 1)");
    }

    const auto len = static_cast<size_t>(info.size);
    std::vector<uint8_t> v(len);
    std::memcpy(v.data(), info.ptr, len);

    // Prevent overly-aggressive dead-code elimination in case this is inlined.
    if (len > 0) {
        volatile uint8_t sink = v[0];
        (void) sink;
    }

    return v.size();
}

PYBIND11_MODULE(pybind11_case, m) {
    m.def("vec_len", &vec_len);
    m.def("buffer_copy_len", &buffer_copy_len);
}


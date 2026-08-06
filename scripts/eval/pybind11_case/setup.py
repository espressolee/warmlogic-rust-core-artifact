from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext

ext_modules = [
    Pybind11Extension(
        "pybind11_case",
        ["pybind11_case.cpp"],
        cxx_std=17,
    ),
]

setup(
    name="pybind11_case",
    version="0.0.0",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
)


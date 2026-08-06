from setuptools import Extension, setup

from Cython.Build import cythonize

extensions = [
    Extension(
        name="cython_case",
        sources=["cython_case.pyx"],
        language="c++",
        extra_compile_args=["-O3", "-std=c++17"],
    )
]

setup(
    name="cython_case",
    version="0.0.0",
    ext_modules=cythonize(extensions, compiler_directives={"language_level": "3"}),
)


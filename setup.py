import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="insar",
    version="1.1.3",
    author="Scott Staniewicz",
    author_email="scott.stanie@utexas.com",
    description="Tools for gathering and preprocessing InSAR data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/scottstanie/insar",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=(
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: C",
        "License :: OSI Approved :: MIT License",
        "Topic :: Scientific/Engineering",
        "Intended Audience :: Science/Research",
    ),
    install_requires=["numpy", "scipy", "requests", "matplotlib", "click"],
    entry_points={
        "console_scripts": [
            "insar=insar.scripts.cli:cli",
        ],
    },
    ext_modules=[
        setuptools.Extension(
            "insar.c_upsample", ["insar/c_upsample.pyx"], extra_compile_args=["-O3", "-std=gnu99"])
    ],
    zip_safe=False)

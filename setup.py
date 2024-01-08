#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import os

from setuptools import find_packages, setup


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return codecs.open(file_path, encoding="utf-8").read()


setup(
    name="pytest-oof",
    version="2.0.0",
    author="Jeff Wright",
    author_email="jeff.washcloth@gmail.com",
    license="MIT",
    url="https://github.com/jeffwright13/pytest-oof",
    description="pytest-oof: pytest Outcomes & Output-Fields: - a plugin providing structured, programmatic access to a test run's results as rendered in console",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    py_modules=["pytest_oof"],
    python_requires=">=3.8",
    install_requires=[
        "from-root==1.3.0",
        "ansi2html==1.8.0",
        "json2table==1.1.5",
        "pytest-metadata==2.0.4",
        "rich>=10.6.0",
        "single-source>=0.3.0",
        "strip-ansi>=0.1.1",
        "textual==0.1.18",
    ],
    setup_requires=["setuptools_scm"],
    include_package_data=True,
    classifiers=[
        "Framework :: Pytest",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
    ],
    keywords="pytest pytest-plugin testing",
    entry_points={
        "pytest11": ["pytest_oof = pytest_oof.plugin"],
        "console_scripts": [
            "oofda = pytest_oof.__main__:main",
            "oof-console = pytest_oof.clients.console_gen:main",
            "oof-html = pytest_oof.clients.html_gen:main",
            "oof-tui = pytest_oof.clients.tui_gen:main",
        ],
    },
)

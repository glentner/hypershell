# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import datetime
sys.path.insert(0, os.path.abspath('../..'))

import hypershell  # noqa

# -- Project information -----------------------------------------------------

year = datetime.datetime.now().year
project = 'hyper-shell'
copyright = f'2019-{year} Geoffrey Lentner'  # noqa: shadows builtin name?
author = 'Geoffrey Lentner <glentner@purdue.edu>'

# The full version, including alpha/beta/rc tags
release = hypershell.__version__
version = hypershell.__version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.extlinks',
    'sphinx.ext.viewcode',
    'sphinxext.opengraph',
    'sphinx_sitemap',
    'sphinx_inline_tabs',
    'sphinx_copybutton',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'default'  # default: sphinx

# -- Options for HTML output -------------------------------------------------

html_title = 'HyperShell v2'
html_baseurl = 'https://hyper-shell.readthedocs.io'
html_theme = 'furo'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# export variables with epilogue
rst_epilog = f"""
.. |release| replace:: {release}
.. |copyright| replace:: {copyright}
"""


# manual pages options
man_pages = [(
    'manual',
    'hyper-shell',
    'Process shell commands over a distributed, asynchronous queue',
    'Geoffrey Lentner <glentner@purdue.edu>.',
    '1'
),
]

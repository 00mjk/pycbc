################
Installing PyCBC
################

There are three typical use cases for PyCBC:

1. Installing a release of PyCBC from GitHub for an end user to run the tools.
2. Installing an editable version from GitHub for development.
3. Production LIGO analyses.

This page documents the first two use cases. For production analysis, users must obtain the pre-built binaries from the PyCBC server. 

If you wish to develop PyCBC, then you will need an account on `GitHub <https://www.github.com>`_ Once you have set up your account you should follow the instructions to `fork a repository <https://help.github.com/articles/fork-a-repo/>`_ to fork the `ligo-cbc/pycbc <https://github.com/ligo-cbc/pycbc>`_ repository into your own account.

=============
Getting started
=============

The reccomended way of installing PyCBC is to use `pip <https://pip.pypa.io/en/stable/>`_ within a `Python Virtual Envionment <https://virtualenv.pypa.io/en/latest/>`_. Virtualenv isolates PyCBC and its dependencies from the system environment and installing with pip ensures that PyCBC picks up the correct dependencies. 

If you do not have virtualenv installed (as is the case with LIGO Data Grid Scientific Linux systems), you will need to perform a one-time setup to get virtualenv installed in your environment. To do this see the instructions at

.. toctree::
    :maxdepth: 1

    virtualenv_install

===========================
Creating a virtualenv
===========================

Installing PyCBC into a virtual environment provides isolation between different sets of python packages. The following instructions will create a working PyCBC environment on an LDG cluster. 

Make sure that you have at least version 13.1.1 of virtualenv by running 

.. code-block:: bash

    virtualenv --version
    
If this returns virtualenv: command not found or a lower version, see the instructions above for installing virtualenv.

The first task is to clear out your current PYTHONPATH in case you had been using that before. To do this, run the command:

.. code-block:: bash

    unset PYTHONPATH

By default, virtualenv will modify your shell prompt so that it prepends the name of the virtual environment. This can be useful to make sure that you are developing in the virtual environment, or if you have several virtual environments. However, if you do not want this, then set

.. code-block:: bash

    VIRTUAL_ENV_DISABLE_PROMPT=True
    
Before running the command to create the new virtual environment.

Next, you need to choose a directory name where you'd like to make your virtual environment, and then make it. In this example, we use ${HOME}/pycbc-dev but this can be changed to any path other than a directory under ${HOME}/.local: 

.. code-block:: bash

    NAME=${HOME}/pycbc-dev
    virtualenv $NAME
    
To enter your virtual environment run the command

.. code-block:: bash
    
    source $NAME/bin/activate
    
You will now be 'inside' your virtual environment, and so you can install packages, etc, without conflicting with either the system build, or other builds that you may have sitting around. You may install c-dependencies such as lalsuite (:ref:`lalsuite_install`), or rely on the system versions.

To leave this virtual environment type

.. code-block:: bash

    deactivate
    
which will return you to a regular shell.

===========================
Installing PyCBC in a virtualenv
===========================

Enter the virtual enviornment that you wish to use for PyCBC development by sourcing the activate script, as shown in the previous section.

Install pycbc from source as follows. First install unittest2 and numpy with the command:

.. code-block:: bash

    pip install "numpy>=1.6.4" unittest2
    
You now need to decide whether you want to install a release of PyCBC for end-use, or an editable git repository for development. 

To install a release of the code, determine the tag of the relase that you want to install from the `list of PyCBC tags <https://github.com/ligo-cbc/pycbc/tags>`_. This example installs the v1.1.0 release. If you want to install a different release, change the command below accordingly:

.. code-block:: bash

    pip install git+https://github.com/ligo-cbc/pycbc@v1.1.0#egg=pycbc --process-dependency-links

To install and editable version of PyCBC you need to have `forked PyCBC to your own account <https://help.github.com/articles/fork-a-repo/>`_ and know the URL of your fork. This can be obtained from the clone URL on your GitHub repository page. This example uses the URL git@github.com:duncan-brown/pycbc.git which you should change as appropriate. You can read the `pip git instructions <https://pip.pypa.io/en/latest/reference/pip_install.html#git>`_ for more details on how to install a branch or a specific tag.

.. code-block:: bash

    pip install -e git+git@github.com:duncan-brown/pycbc.git#egg=pycbc --process-dependency-links

This will fetch the PyCBC source and will also install all the listed dependenciesl. 

The -e option to pip creates a directory called $NAME/src/pycbc with a git checkout which is fully edittable. To prevent pip from removing this source directory run the command

.. code-block:: bash

    rm -f $NAME/src/pip-delete-this-directory.txt

You can then make changes to your PyCBC source code in the directory $NAME/src/pycbc

To build and install any changes that you make in your virtual environment, run the command

.. code-block:: bash

    python setup.py install
    
from the PyCBC source directory in $NAME/src/pycbc 

=============
Building and Installing Documentation
=============

To build the documentation from your virtual environment, first make sure that you have `Sphinx <http://sphinx-doc.org/>`_ and the required helper tools installed with

.. code-block:: bash

    pip install Sphinx>=1.3.1
    pip install sphinxcontrib-programoutput
    pip install numpydoc
    
To generate the documentation, from the top level of the PyCBC source tree run

.. code-block:: bash

    python setup.py build_docs
    
This will build the documentation in the directory docs/_build/html which can be copied to a web-accessible directory. For example

.. code-block:: bash

    cp -a docs/_build/html/ ~/public_html/pycbc-docs
    
will copy the documentation to a directory called pycbc-docs under your public_html pages.

===============================
Optional GPU acceleration
===============================
PyCBC has the ability to accelerate its processing using CUDA. 

.. toctree::
    :maxdepth: 1

    cuda_install

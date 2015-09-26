#!/bin/bash

# Exit if any command fails
set -e 

#Installing pyCBC

# Ask the user where they want pycbc installed
read -p "Enter the location where you want the virtual env created " NAME

if [[ $NAME == ~* ]] ; then
  if [[ ! "$NAME" =~ "/" ]] ; then
    NAME=${HOME}
  else
    # chomp the ~
    NAME=${NAME/##~}
    # chomp anything else before the first slash to catch e.g. ~alenon/
    NAME=${NAME#*\/}
    # expand to the user's home directory
    NAME=${HOME}/${NAME}
  fi
fi

if [ -z $NAME ] ; then
  echo "ERROR: you must specify a path for your virtual environment"
  exit 1
fi

if [ -d $NAME ] ; then
   echo "ERROR: the directory $NAME already exists."
   echo "If you want to use this path, remove the directory and try again."
   exit 1
fi

read -p "Enter the number of processors that you want to use for builds: " nproc

if [ -z $nproc ] ; then
  nproc=1
fi

echo "Using $nproc processors"

#Create a Virtual Environment
virtualenv $NAME

#Enter Virtual Environment
source $NAME/bin/activate
mkdir -p $VIRTUAL_ENV/src

#Install HDF5
cd $VIRTUAL_ENV/src
curl https://www.hdfgroup.org/ftp/HDF5/releases/hdf5-1.8.12/src/hdf5-1.8.12.tar.gz > hdf5-1.8.12.tar.gz
tar -zxvf hdf5-1.8.12.tar.gz
rm hdf5-1.8.12.tar.gz
cd hdf5-1.8.12
./configure --prefix=$VIRTUAL_ENV/opt/hdf5-1.8.12
make -j $nproc install
HDF5_DIR=${VIRTUAL_ENV}/opt/hdf5-1.8.12 pip install h5py

#Installing lalsuite into Virtual Environment
#Install unitest2, python-cjson, and numpy
pip install "numpy>=1.6.4" unittest2 python-cjson Cython

#Authenticate with LIGO Data Grid services, install M2Crypto
SWIG_FEATURES="-cpperraswarn -includeall -I/usr/include/openssl" pip install M2Crypto

read -p "Enter you LIGO.ORG username in (e.g. albert.einstein): " directory

#Valid ECP cookie to clone
echo "Enter your LIGO.ORG password to get a cookie to clone lalsuite"
ecp-cookie-init LIGO.ORG https://versions.ligo.org/git $directory

#Tell git the location of the cookie
git config --global http.cookiefile /tmp/ecpcookie.u`id -u`

#Get Copy of LalSuite Repository
cd $VIRTUAL_ENV/src
git clone https://versions.ligo.org/git/lalsuite.git
 
#Obtaining source code and checking version
#Change to lalsuite directory
cd lalsuite

#Determine which version of the code you want to install
echo "Enter the name of the lalsuite branch that you want to use"
read -rp "(e.g. master or lalsuite_o1_branch) " lalbranch
git checkout $lalbranch

#Building and Installing into your Virtual Environment
#Use the master configure script to build and install all the components
./00boot
./configure --prefix=${VIRTUAL_ENV}/opt/lalsuite --enable-swig-python --disable-lalstochastic --disable-lalxml --disable-lalinference --disable-laldetchar
make -j $nproc
make install

#Add to virtualenv activate script
echo 'source ${VIRTUAL_ENV}/opt/lalsuite/etc/lalsuiterc' >> ${VIRTUAL_ENV}/bin/activate
source ${VIRTUAL_ENV}/opt/lalsuite/etc/lalsuiterc

#Check that lalsuite is installed
echo $LAL_PREFIX

#Installing pyCBC to Virtual Environment

#Install Pegasus WMS python libraries
pip install http://download.pegasus.isi.edu/pegasus/4.5.2/pegasus-python-source-4.5.2.tar.gz

#Install dqsegb from Duncan's repository
pip install git+https://github.com/duncan-brown/dqsegdb.git@pypi_release#egg=dqsegdb

#Released or Development
echo Would you like to install a released version or development version?
echo "1. Release version"
echo "2. Development version"
read -rp "Enter either 1 or 2: " dev_or_rel

if [ $dev_or_rel -eq 1 ] ; then
#Installing a released version of pyCBC
#Choose release version
read -rp "Enter the release tag that you want to install (e.g. v1.1.5) " reltag

#Install Version
pip install git+https://github.com/ligo-cbc/pycbc@${reltag}#egg=pycbc --process-dependency-links

elif [ $dev_or_rel -eq 2 ] ; then

  #Fork pyCBC to your Github account
  echo For the development version, you will need a GitHub account.
  echo If you do not have a github account you will need to set one up.
  echo Follow the instruction on https://help.github.com/articles/fork-a-repo/ to fork your GitHub account to PyCBC.
  echo You will then need to enable ssh keys on your GitHub account. You can follow these instructions: https://help.github.com/articles/generating-ssh-keys/
  read -rsp $'Once you have finished that press [Enter] to continue...\n' -n1 key

  #Input Username
  read -rp "GitHub Username: " github

  #Install PyCBC source code from GitHub URL
  pip install -e git+git@github.com:$github/pycbc.git#egg=pycbc --process-dependency-links

  #Prevent Pip from removing source directory
  rm -f ${VIRTUAL_ENV}/src/pip-delete-this-directory.txt

else

echo "You must enter 1 or 2"
exit 1

fi

#Building and Installing Documentation
#Install Sphinx and the helper tools
pip install "Sphinx>=1.3.1"
pip install sphinxcontrib-programoutput
pip install numpydoc

#patch the bug in numpydoc for python 2.6
cat <<EOF > ${VIRTUAL_ENV}/plot_directive.patch
--- /home/dbrown/src/pycbc/lib/python2.6/site-packages/matplotlib/sphinxext/plot_directive.py	2015-09-24 20:30:54.057566343 -0400
+++ /home/dbrown/projects/aligo/pycbc-docs/lib/python2.6/site-packages/matplotlib/sphinxext/plot_directive.py	2015-09-26 11:01:58.000000000 -0400
@@ -333,13 +333,8 @@
     """
     Remove the coding comment, which six.exec_ doesn't like.
     """
-    try:
-      return re.sub(
+    return re.sub(
         "^#\s*-\*-\s*coding:\s*.*-\*-$", "", text, flags=re.MULTILINE)
-    except TypeError:
-      return re.sub(
-        "^#\s*-\*-\s*coding:\s*.*-\*-$", "", text, re.MULTILINE)
-      
 
 #------------------------------------------------------------------------------
 # Template
EOF
patch -p0 ${VIRTUAL_ENV}/lib/python2.6/site-packages/matplotlib/sphinxext/plot_directive.py < ${VIRTUAL_ENV}/plot_directive.patch
rm ${VIRTUAL_ENV}/plot_directive.patch

#Add script that sets up the MKL environment to virtualenv activate script
echo 'source /opt/intel/bin/compilervars.sh intel64' >> ${VIRTUAL_ENV}/bin/activate

deactivate

echo "PyCBC has been installed in a virtual environment in $NAME"
echo "To run, type"
echo "  source $NAME/bin/activate"
echo

exit 0

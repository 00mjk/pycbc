# Copyright (C) 2012  Alex Nitz
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


#
# =============================================================================
#
#                                   Preamble
#
# =============================================================================
#

# Check for optional components
have_cuda=False
have_opencl=False

try:
    import pycuda
    import pycuda.gpuarray
    import pycuda.autoinit
    have_cuda=True
except ImportError:
    have_cuda=False
    
try:
    import pyopencl
    import pyopencl.array
    have_opencl=True
except ImportError:
    have_opencl=False


__author__ = "Alex Nitz <alex.nitz@ligo.org>"


current_context=None

class CPUContext(object):
    def __init__(self):
        self.device_context = None
        self.prior_context = None

    def __enter__(self):

        #Save the old context so it can be restored and set the current context
        # to this object 
        self.prior_context=current_context
        current_context=self
        return self

    def __exit__(self,type,value,tracebook):

        #Restore the prior context
        current_context = prior_context

if have_cuda:
    class CUDAContext(object):
        def __init__(self):
            self.device_context = None
            self.prior_context = None
            
        
        def __enter__(self):
            #Save the old context so it can be restored and set the current context
            # to this object 
            self.prior_context=current_context
            current_context=self
            return self

        def __exit__(self,type,value,tracebook):

            #Restore the prior context
            current_context = prior_context

if have_opencl:
    class OpenCLContext(object):

        def __init__(self):
            self.device_context = pyopencl.create_some_context()
            self.queue = pyopencl.CommandQueue(self.device_context)   
            self.prior_context = None

        def __enter__(self): 
            #Save the old context so it can be restored and set the current context
            # to this object 
            self.prior_context=current_context
            current_context=self
            return self

        def __exit__(self,type,value,tracebook):

            #Restore the prior context
            current_context = prior_context
    
#Set the default Processing Context to be the CPU
current_context=CPUContext()


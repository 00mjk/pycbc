# Copyright (C) 2011 Karsten Wiesner
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
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
"""
pycbc management and tools
"""

from pycbcopencl import cl_context_t as OpenClContext
from pycbccpu import cpu_context_t as CpuContext

# I agree on changing the all too generic naming of datavectors in the C layer
# to real_vector_single_cpu_t real_vector_single_cuda_t real_vector_single_opencl_t
# and so on for the other data types 
from datavector.datavectorcpu import real_vector_single_t as real_vector_single_cpu_t

from abc import ABCMeta, abstractmethod, abstractproperty

import logging

# ------------------- pycbc processing base classes section --------------------

# data_in prototyping and generic ProcessingObj inheritance showcase
# 

# All processing objects have to inherit from this base class via ...
class PyCbcProcessingObj:

    __metaclass__ = ABCMeta

    def __init__(self, device_context):
        self._logger= logging.getLogger('pycbc.pycbc')
        self._devicecontext = device_context

    @abstractmethod
    def data_in(self, datavector):
        pass

# ... their correct derivative according to their processing architecture:
class CpuProcessingObj(PyCbcProcessingObj):

    def __init__(self, device_context):
    
        super(CpuProcessingObj, self).__init__(device_context)

    # data_in() is to be called for every input datavector. 
    # in case of an alien datavector (does not fit to self-architecture) data_in
    # create the new datavector, copies the data by calling the proper transfer 
    # function in the C layer and set new_datavector = old_datavector 
    # (thus destroy the old datavector)

    def data_in(self, datavector):

        print 'data_in of ' + repr(self) + ' called'
        print 'with ' + repr(datavector)
        
        if repr(datavector).find("datavectorcpu") >= 0:
            # it is one of us
            return datavector

        else:
            print 'aliendatavector found:'
            alien_repr_str= repr(datavector)
            print alien_repr_str
            # find correct new datatype. by parsing alien_repr_str.
            # and instanciate the correct thing, " cloning " from the alien
            new_arch_vector = real_vector_single_cpu_t(len(datavector), datavector.get_delta_x())
            
            # call the transfer function in the C layer
            # prototyping it here:
            for i in range(len(datavector)):
                new_arch_vector[i] = datavector[i]
            
            return new_arch_vector

# ------------------- device context section -----------------------------------

class CpuDeviceContext:

    def __init__(self, devicehandle):
        self.__logger= logging.getLogger('pycbc.pycbc')
        self.__devicehandle = devicehandle
        self.__logger.debug("instanciated CpuDeviceContext {0}".format(self.__devicehandle))

        # create Cpu device context
        self.__cpucontext = CpuContext(self.__devicehandle)
        self.__logger.debug( repr(self.__cpucontext) )
        self.__logger.debug( str(self.__cpucontext) )


    def __enter__(self):
        self.__logger.debug("__enter__ called ")
        
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__logger.debug("__exit__ called ")
        # destroy Cpu device context
        del(self.__cpucontext)
        
        
class OpenClDeviceContext:

    def __init__(self, devicehandle):
        self.__logger= logging.getLogger('pycbc.pycbc')
        self.__devicehandle = devicehandle
        self.__logger.debug("instanciated OpenClDeviceContext {0}".format(self.__devicehandle))

    def __enter__(self):
        self.__logger.debug("__enter__ called ")
        
        # create OpenCl device context
        self.__openclcontext = OpenClContext(self.__devicehandle)
        self.__logger.debug( repr(self.__openclcontext) )
        self.__logger.debug( str(self.__openclcontext) )
                
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__logger.debug( "__exit__ called " )
        # destroy OpenCl device context
        del(self.__openclcontext)
        
    #-properties----------------------------------------------------------------

    #@property
    #def con(self):
    #    return self.__openclcontext

        

class CudaDeviceContext:

    def __init__(self, devicehandle):
        self.__logger= logging.getLogger('pycbc.pycbc')
        self.__devicehandle = devicehandle
        self.__logger.debug("instanciated CudaDeviceContext {0}".format(self.__devicehandle))


    def __enter__(self):
        self.__logger.debug("__enter__ called ")
        
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__logger.debug("__exit__ called ")
        

        
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
# ==============================================================================
#
#                                   Preamble
#
# ==============================================================================
#
"""
Cpu version of strain data class
"""

# Import base classes
from straindata_base import StrainDataBase
from straindata_base import FftSegmentsImplementationBase

# import member datavectors
from pycbc.datavector.datavectorcpu import real_vector_double_cpu_t
from pycbc.datavector.datavectorcpu import real_vector_single_cpu_t
from pycbc.datavector.datavectorcpu import complex_vector_single_cpu_t

# Swigged C-layer functions
from straindatacpu import fftw_generate_plan
from straindatacpu import fftw_transform_segments

import logging


class StrainDataCpu(StrainDataBase):
    """
    CPU derivate of straindata class
    """
    
    def __init__(self, t_start, t_end, n_segments, sample_freq, interferometer):
        """
        Constructor of the straindata class
        @type t_start: int
        @param t_start: GPS start time of the strain data 
        @type t_end: int
        @param t_end: GPS start time of the strain data
        @type n_segments: int
        @param n_segments: Number of the overlapping segments to transform
        @type sample_freq: double
        @param sample_freq: Sample frequency in Hz
        @type interferometer: string
        @param interferometer: Interferometer name (H0, H1, L1 etc.) 
        @rtype: none
        @return: none
        """
    
        super(StrainDataCpu, self).__init__(t_start, t_end, n_segments, 
                    sample_freq, interferometer,
                    initial_time_series_t = real_vector_double_cpu_t,
                    time_series_t =         real_vector_single_cpu_t,
                    frequency_series_t=     complex_vector_single_cpu_t,
                    fft_segments_impl_t=    FftSegmentsImplementationFftw)

    def render(self):
        """
        Renders straindata to the final processing architecture (ig. transfer
        the data to the GPU by copy it into a datavectoropencl memory object) 
        @rtype: none
        @return: none
        """
        pass         # nothing to render in cpu version (data remaines in place)
                                            
                                                                                                                                                                          
class  FftSegmentsImplementationFftw(FftSegmentsImplementationBase):
    """
    Implementation class of segmentation and fourier transform on 
    CPU architecture (currently we will perform this task exclusively
    on the CPU because it is out of the hot loop. Hence it consumes relatively 
    low computepower)
    """

    def __init__(self, segments_length, overlap_fact, input_buf_t, 
                 output_buffer_t):
        """
        Constructor of the segmenting-implementation class
        @type length: int
        @param length: segments length 
        @type overlap_fact: double
        @param overlap_fact: overlapping factor
        @type input_buf_t: class
        @param input_buf_t: class of inputbuffer(ig. real_vector_single_cpu_t)
        @type output_buffer_t: class
        @param output_buffer_t: class of inputbuffer(ig.complex_vector_single_cpu_t)
        @rtype: none
        @return: none
        """
        
        self.__logger= logging.getLogger('pycbc.FftSegmentsImplementationFftw')

        assert repr(input_buf_t).find("datavectorcpu") >= 0, "try to \n\
        instanciate FftSegmentsImplementationFftw CPU implementation with \n\
        wrong type of datavector for input_buf"
        
        assert repr(output_buffer_t).find("datavectorcpu") >= 0, "try to \n\
        instanciate FftSegmentsImplementationFftw CPU implementation with \n\
        wrong type of datavector for output_buffers_t"

        super(FftSegmentsImplementationFftw, self).__init__()

        self.__segments_length = segments_length
        self.__overlap_fact = overlap_fact
        self.__input_buf_t = input_buf_t
        self.__output_buffer_t =  output_buffer_t

        # create fft plan
        delta_x_tmp = 1.0 # not used in fft plan generation, just for 
                          # datavector constructor
        in_tmp  = self.__input_buf_t(segments_length, delta_x_tmp)
        out_tmp = self.__output_buffer_t(segments_length, delta_x_tmp)
        self.__fft_forward_plan= fftw_generate_plan(segments_length, in_tmp, 
        out_tmp, "FFTW_FORWARD", "FFTW_ESTIMATE")

        self.__logger.debug("instanciated FftSegmentsImplementationCpu")
    
    def fft_segments(self, input_buf, output_buf):
        """
        Process ffts of strain data segments
        @type input_buf: data_vector
        @param input_buf: input buffer
        @type output_buffer: data_vector
        @param output_buffer: output buffer
        @rtype: none
        @return: none

        """
        
        self.__logger.debug("performing fft w/ plan {0}".
        format(self.__fft_forward_plan))

        input_buf_offset = 0
        for output_buffer_segment in output_buf:
            self.__logger.debug("input_buf_offset: {0}".
            format(input_buf_offset))
            fftw_transform_segments(self.__fft_forward_plan, input_buf, 
                                    input_buf_offset, output_buffer_segment)
            input_buf_offset = int( input_buf_offset + self.__segments_length * 
                                    (1 - self.__overlap_fact) )
                                    

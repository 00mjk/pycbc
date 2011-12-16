# Copyright (C) 2011 Karsten Wiesner, Drew Keppel
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
Waveform Generator Cpu implementation class for the pycbc package
"""

from pycbc.cpu import CpuProcessingObj
from pycbc.waveformgenerator.base import WaveFormGeneratorBase

from pycbc.waveformgenerator.clayer.waveformgeneratorcpu import gen_precon_vector_TaylorF2
from pycbc.waveformgenerator.clayer.waveformgeneratorcpu import gen_waveform_filter_TaylorF2

import logging

class WaveFormGeneratorCpu(WaveFormGeneratorBase, CpuProcessingObj):

    def __init__(self, 
                 context, 
                 waveform_length=0, 
                 waveform_delta_x=1,
                 approximation_model=None,
                 waveform_filter=None):
                 
        self.__logger= logging.getLogger('pycbc.WaveFormGeneratorCpu')
        self.__logger.debug("instanciate WaveFormGeneratorCpu")
        
        super(WaveFormGeneratorCpu, self).__init__(
                                context,  
                                approximation_model=approximation_model)
                                
        # mapping clayer functions according to approximation model
        self.__logger.debug("Using approximation model " + 
            "{0}".format(self._approximation_model))
        
        gen_precon_map={
            "TaylorF2":GenPreconVecTaylorF2(), 
            "SpinTaylorT4":None
            }
        self.__logger.debug("created a map of aproximation-models to " +
            "generate_precondition-functors {0}".format(gen_precon_map))
        
        self.gen_precon_vector = gen_precon_map[self._approximation_model]
        self.__logger.debug("mapped gen_precon_vector functor to " + 
            "{0}".format(self.gen_precon_vector))
        
        gen_waveform_filter_from_row_map = {
            "TaylorF2":GenWaveformFilterTaylorF2FromRow(),
            "SpinTaylorT4":None
            }
        self.__logger.debug("created a map of aproximation-models to " +
            "generate_waveform_filter_from_row-functors " +
            "{0}".format(gen_waveform_filter_from_row_map))

        self.gen_waveform_filter_from_row = \
            gen_waveform_filter_from_row_map[self._approximation_model]
        self.__logger.debug("mapped self.gen_waveform_filter_from_row functor to " +
            "{0}".format(self.gen_waveform_filter_from_row))

        gen_waveform_filter_map = {
            "TaylorF2":GenWaveformFilterTaylorF2(),
            "SpinTaylorT4":None
            }
        self.__logger.debug("created a map of aproximation-models to " +
            "generate_waveform_filter-functors "
            "{0}".format(gen_waveform_filter_map))

        self.gen_waveform_filter = \
            gen_waveform_filter_map[self._approximation_model]
        self.__logger.debug("mapped self.gen_waveform_filter functor to " +
            "{0}".format(self.gen_waveform_filter))


    # implementation of ABC's abstractmethod
    def perform_generate_precondition_factor(self, length, delta_x, pre_condition_vector_t):

        self.__logger.debug("called perform_generate_precondition_factor")

        # pre instanciate precon vector
        precon_vec = pre_condition_vector_t(self._devicecontext, length, delta_x)

        # depending on the approx model and thus on the implementation of
        # self.clayer generate_precondition() would return True or False
        # if false return none if true return precon vec! 

        if self.gen_precon_vector(precon_vec):
            return precon_vec
        else:
            return None        

    # implementation of ABC's abstractmethod
    def perform_generate_waveform_filter(self, waveform_filter, **kwargs):

        self.__logger.debug("called perform_generate_waveform_filter")

        self.gen_waveform_filter(waveform_filter, **kwargs)

        return self._waveform_filter

    # implementation of ABC's abstractmethod
    def perform_generate_waveform_filter_from_row(self, waveform_filter, template):

        self.__logger.debug("called perform_generate_waveform_filter")

        self.gen_waveform_filter(waveform_filter, template)

        return self._waveform_filter


## Functors for the TaylorF2 approximant
class GenPreconVecTaylorF2:
    """
    functor definition for gen_precon_vector_TaylorF2
    """

    def __init__(self):
        # status variables etc for/in clayer regrading this function goes here !
        pass

    def __call__(self, precon_vec ):

        return gen_precon_vector_TaylorF2(precon_vec)

class GenWaveformFilterTaylorF2:
    """
    functor definition for gen_waveform_filter_TaylorF2
    """

    def __init__(self):
        self.__logger= logging.getLogger('pycbc.GenWaveformFilterTaylorF2')
        self.__logger.debug("instanciate GenWaveformFilterTaylorF2")

        # status variables etc for/in clayer regrading this function goes here !

    def __call__(self, waveform_filter, **kwargs):

	## used_kwargs lists the kwargs that are needed for this approximant
	used_kwargs = ['mass1', 'mass2']

	for kwarg in used_kwargs:
		if kwarg not in kwargs:
			self.__logger.debug("missing kwarg {0}".format(kwarg))
			raise KeyError

	for kwarg in kwargs:
		if kwarg not in used_kwargs:
			self.__logger.debug("unused kwarg {0}".format(kwarg))
			raise Warning

	mass1 = kwargs['mass1'] #FIXME: need to multiply by solar_mass in kg
	mass2 = kwargs['mass2'] #FIXME: need to multiply by solar_mass in kg

        gen_waveform_filter_TaylorF2(waveform_filter, mass1, mass2)

class GenWaveformFilterTaylorF2FromRow:
    """
    functor definition for gen_waveform_filter_TaylorF2_from_row
    """

    def __init__(self):
        # status variables etc for/in clayer regrading this function goes here !
        pass

    def __call__(self, waveform_filter, template):

        mass1 = template.mass1 #FIXME: need to multiply by solar_mass in kg
        mass2 = template.mass2 #FIXME: need to multiply by solar_mass in kg

        gen_waveform_filter_TaylorF2(waveform_filter, mass1, mass2)


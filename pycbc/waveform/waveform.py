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
"""Convenience functions to genenerate gravitational wave templates and
waveforms.
"""
import sys
import lal
import lalsimulation
from pycbc.types import TimeSeries,FrequencySeries,zeros,Array,complex_same_precision_as
from pycbc import HAVE_CUDA,HAVE_OPENCL
from pycbc.scheme import mgr
import pycbc.scheme as _scheme
import inspect
from pycbc.fft import fft

#FIXME#################### REMOVE THESE WHEN FEATURES AVAILABLE IN LALSIMULATION 
lalsim_approx = {'SpinTaylorT4':lalsimulation.SpinTaylorT4,
                'TaylorT4':lalsimulation.TaylorT4,
                'TaylorT3':lalsimulation.TaylorT3,
                'TaylorT2':lalsimulation.TaylorT2,
                'TaylorT1':lalsimulation.TaylorT1,
                'EOBNRv2':lalsimulation.EOBNRv2,
                'SEOBNRv1':lalsimulation.SEOBNRv1,
                'IMRPhenomB':lalsimulation.IMRPhenomB}

lalsim_approx_names = ['SpinTaylorT4','TaylorT1','TaylorT2',
                       'TaylorT3','TaylorT4','EOBNRv2','SEOBNRv1','IMRPhenomB']
                       
lalsim_fd_approx = {'TaylorF2':lalsimulation.TaylorF2,'IMRPhenomB':lalsimulation.IMRPhenomB}
lalsim_fd_names = ['TaylorF2','IMRPhenomB']


#FIXME######################################### RELOCATE THIS TO ANOTHER MODULE

def solar_mass_to_kg(solar_masses):
    return solar_masses * lal.LAL_MSUN_SI
    
def parsecs_to_meters(distance):
    return distance *lal.LAL_PC_SI




default_args = {'spin1x':0,'spin1y':0,'spin1z':0,
                'spin2x':0,'spin2y':0,'spin2z':0,
                'inclination':0,'distance':10e8,'fmax':0,'phi0':0,
                'amplitude_order':-1,'phase_order':-1}

def _lalsim_td_waveform(p):
    try:
        hp,hc = lalsimulation.SimInspiralChooseTDWaveform(float(p['phi0']),
                   float(p['delta_t']),
                   float(solar_mass_to_kg(p['mass1'])),
                   float(solar_mass_to_kg(p['mass2'])),
                   float(p['spin1x']),float(p['spin1y']),float(p['spin1z']),
                   float(p['spin2x']),float(p['spin2y']),float(p['spin2z']),
                   float(p['f_lower']),0,
                   parsecs_to_meters(float(p['distance'])),
                   float(p['inclination']),
                   0,0,0,
                   int(p['amplitude_order']),int(p['phase_order']),
                   lalsim_approx[p['approximant']])
    except KeyError as e:
        raise type(e), type(e)("Missing value for " + e.message), sys.exc_info()[2]
    return hp,hc

def _lalsim_fd_waveform(p):
    try:
        htilde = lalsimulation.SimInspiralChooseFDWaveform(float(p['phi0']),
                   float(p['delta_f']),
                   float(solar_mass_to_kg(p['mass1'])),
                   float(solar_mass_to_kg(p['mass2'])),
                   float(p['spin1x']),float(p['spin1y']),float(p['spin1z']),
                   float(p['spin2x']),float(p['spin2y']),float(p['spin2z']),
                   float(p['f_lower']),0,
                   parsecs_to_meters(float(p['distance'])),
                   float(p['inclination']),
                   0,0,0,
                   int(p['amplitude_order']),int(p['phase_order']),
                   lalsim_fd_approx[p['approximant']])
    except KeyError as e:
        raise type(e), type(e)("Missing value for " + e.message), sys.exc_info()[2]
    return htilde

def _filter_td_waveform(p):
    raise NotImplementedError

def _filter_fd_waveform(p):
    raise NotImplementedError

def _cuda_td_waveform(p):
    raise NotImplementedError

def _cuda_fd_waveform(p):
    raise NotImplementedError

def _opencl_td_waveform(p):
    raise NotImplementedError

def _opencl_fd_waveform(p):
    raise NotImplementedError


# td, fd, filter waveforms generated on the CPU
_lalsim_td_approximants = {}
for approx in lalsim_approx:
    _lalsim_td_approximants[approx] = _lalsim_td_waveform

_lalsim_fd_approximants = {}
for approx in lalsim_fd_approx:
    _lalsim_fd_approximants[approx] = _lalsim_fd_waveform

# Waveforms that are optimized to work as filters
_filter_fd_approximants = {}
_filter_td_approximants = {}

cpu_td = _lalsim_td_approximants
cpu_fd = _lalsim_fd_approximants
cpu_td_filter =  dict(_filter_td_approximants.items() + _filter_td_approximants.items() + _lalsim_td_approximants.items())
cpu_fd_filter =  dict(_lalsim_fd_approximants.items() + _filter_fd_approximants.items())

# Waveforms written in CUDA
_cuda_td_approximants = {}
_cuda_fd_approximants = {}

cuda_td = dict(_lalsim_td_approximants.items() + _cuda_td_approximants.items())
cuda_fd = dict(_lalsim_fd_approximants.items() + _cuda_fd_approximants.items())
cuda_td_filter = dict(cpu_td_filter.items() + cuda_td.items())
cuda_fd_filter = dict(cpu_fd_filter.items() + cuda_fd.items())

# Waveforms written in OpenCL
_opencl_td_approximants = {}
_opencl_fd_approximants = {}

opencl_td = dict(_lalsim_td_approximants.items() + _opencl_td_approximants.items())
opencl_fd = dict(_lalsim_fd_approximants.items() + _opencl_fd_approximants.items())
opencl_td_filter = dict(cpu_td_filter.items() + opencl_td.items())
opencl_fd_filter = dict(cpu_fd_filter.items() + opencl_fd.items())

td_wav = {type(None):cpu_td,_scheme.CUDAScheme:cuda_td,_scheme.OpenCLScheme:opencl_td}

fd_wav = {type(None):cpu_fd,_scheme.CUDAScheme:cuda_fd,_scheme.OpenCLScheme:opencl_fd}

td_filter = {type(None):cpu_td_filter,_scheme.CUDAScheme:cuda_td_filter,_scheme.OpenCLScheme:opencl_td_filter}
fd_filter = {type(None):cpu_fd_filter,_scheme.CUDAScheme:cuda_fd_filter,_scheme.OpenCLScheme:opencl_fd_filter}

def list_td_approximants():
    print("Lalsimulation Approximants")
    for approx in _lalsim_td_approximants.keys():
        print "  " + approx
    print("CUDA Approximants")
    for approx in _cuda_td_approximants.keys():
        print "  " + approx
    print("OpenCL Approximants")
    for approx in _opencl_td_approximants.keys():
        print "  " + approx
    
def list_fd_approximants():
    print("Lalsimulation Approximants")
    for approx in _lalsim_fd_approximants.keys():
        print "  " + approx
    print("CUDA Approximants")
    for approx in _cuda_fd_approximants.keys():
        print "  " + approx
    print("OpenCL Approximants")
    for approx in _opencl_fd_approximants.keys():
        print "  " + approx
    
def list_filter_approximants():
    pass

def props(obj,**kwargs):
    pr = {}
    if obj is not None:
        for name in dir(obj):
            try:
                value = getattr(obj, name)
                if not name.startswith('__') and not inspect.ismethod(value):
                    pr[name] = value
            except:
                continue

    # Get the parameters to generate the waveform
    # Note that keyword arguments override values in the template object
    input_params = default_args
    input_params.update(pr)
    input_params.update(kwargs)

    return input_params

def get_td_waveform(template=None,**kwargs):
    """Return the waveform specified by the attributes of the template with 
       overrides given by keyword argument
    """
    input_params = props(template,**kwargs)
    hp,hc = td_wav[type(mgr.state)][input_params['approximant']](input_params)
    hp = TimeSeries(hp.data.data,delta_t=hp.deltaT,epoch=hp.epoch)
    hc = TimeSeries(hc.data.data,delta_t=hc.deltaT,epoch=hc.epoch)
    return (hp,hc)

def get_fd_waveform(template=None,**kwargs):
    """Return the frequency domain waveform specified by the attributes
       of the template with overrides given by keyword argument
    """
    input_params = props(template,**kwargs)
    htilde = fd_wav[type(mgr.state)][input_params['approximant']](input_params)
    htilde = FrequencySeries(htilde.data.data,delta_f=htilde.deltaF,epoch=htilde.epoch)
    return htilde

def get_waveform_filter(length,template=None,**kwargs):
    """Return a frequency domain waveform filter for the specified approximant
    """
    input_params = props(template,**kwargs)

    n = length
    N = (n-1) * 2

    if input_params['approximant'] in fd_filter[type(mgr.state)]:
        htilde_lal = fd_filter[type(mgr.state)][input_params['approximant']](input_params)
        htilde_array = Array(htilde_lal.data.data[:])
        htilde = FrequencySeries(zeros(n),delta_f=htilde_lal.deltaF,epoch=htilde_lal.epoch,dtype=htilde_array.dtype)
        htilde[0:len(htilde_array)] = htilde_array[:]
    else:
        hp,hc = td_filter[type(mgr.state)][input_params['approximant']](input_params)
        h_plus =  TimeSeries(zeros(N),delta_t=hp.deltaT,epoch=hp.epoch)
        hp_array = Array(hp.data.data[:])
        h_plus[0:len(hp_array)] = hp_array[:]
        delta_f = 1.0 / N / h_plus.delta_t
        htilde = FrequencySeries(zeros(n),delta_f=delta_f, 
                                   dtype=complex_same_precision_as(h_plus))
        fft(h_plus,htilde) 

    return htilde
    
def precondition_data_for_filter(stilde,approximant):
    raise NotImplementedError












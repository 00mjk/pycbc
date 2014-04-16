from pycbc.types import zeros
import numpy
import ctypes
import functools

def memoize(obj):
    cache = obj.cache = {}

    @functools.wraps(obj)
    def memoizer(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]
    return memoizer

# Note, I do not set the flag to tell fftw that the plan may be used in 
# non-identically aligned memory, this should either be set or aligned memory
# enforced.


#FFTW constants, these are pulled from fftw3.h
FFTW_FORWARD = -1
FFTW_BACKWARD = 1

FFTW_MEASURE = 0
FFTW_DESTROY_INPUT = 1 << 0
FFTW_UNALIGNED = 1 << 1
FFTW_CONSERVE_MEMORY = 1 << 2
FFTW_EXHAUSTIVE = 1 << 3
FFTW_PRESERVE_INPUT = 1 << 4
FFTW_PATIENT = 1 << 5
FFTW_ESTIMATE = 1 << 6
FFTW_WISDOM_ONLY = 1 << 21

# Load the single and double precision libraries
double_lib_name = 'libfftw3.so'
double_lib = ctypes.cdll.LoadLibrary(double_lib_name)
float_lib_name = 'libfftw3f.so'
float_lib = ctypes.cdll.LoadLibrary(float_lib_name)

# Try to import system-wide wisdom files as part of module initialization
# The function is public in case users want to call it again later

def import_sys_wisdom():
    double_lib.fftw_import_system_wisdom()
    float_lib.fftwf_import_system_wisdom()

import_sys_wisdom()
    
# We provide an interface for changing the "measure level"
# By default 1, which does some but not much planning,
# but we provide functions to read and set it

_default_measurelvl = 1
def get_measure_level():
    return _default_measurelvl

def set_measure_level(mlvl):
    global _default_measurelvl
    if mlvl not in (0,1,2,3):
        raise ValueError("Measure level can only be one of 0, 1, 2, or 3")
    _default_measurelvl = mlvl

_flag_dict = {0: FFTW_ESTIMATE,
              1: FFTW_MEASURE,
              2: FFTW_MEASURE|FFTW_PATIENT,
              3: FFTW_MEASURE|FFTW_PATIENT|FFTW_EXHAUSTIVE}
def get_flag(mlvl):
    return _flag_dict(mlvl)

# Create function maps for the dtypes
plan_function = {'float32': {'complex64': float_lib.fftwf_plan_dft_r2c_1d},
                 'float64': {'complex128': double_lib.fftw_plan_dft_r2c_1d},
                 'complex64': {'float32': float_lib.fftwf_plan_dft_c2r_1d,
                             'complex64': float_lib.fftwf_plan_dft_1d,
                              },
                 'complex128': {'float64': double_lib.fftw_plan_dft_c2r_1d,
                                'complex128': double_lib.fftw_plan_dft_1d,
                               }
                }

execute_function = {'float32': {'complex64': float_lib.fftwf_execute_dft_r2c},
                    'float64': {'complex128': double_lib.fftw_execute_dft_r2c},
                    'complex64': {'float32': float_lib.fftwf_execute_dft_c2r,
                                  'complex64': float_lib.fftwf_execute_dft,
                            },
                    'complex128': {'float64': double_lib.fftw_execute_dft_c2r,
                                   'complex128': double_lib.fftw_execute_dft,
                                  }
                   }

def alignment_of(vec):
    """ Return the byte alignment of this array
    """
    pointer = vec.data.ctypes.data
    return double_lib.fftw_alignment_of(pointer)

@memoize
def plan(size, idtype, odtype, direction, mlvl):
    # Convert a measure-level to flags
    flags = get_flag(mlvl)

    if idtype.kind == 'c' and odtype.kind == 'f':
        size = 2*(size - 1)

    # make some representative arrays
    ip = zeros(size, dtype=idtype)
    op = zeros(size, dtype=odtype)

    # Get the plan function
    idtype = numpy.dtype(idtype)
    odtype = numpy.dtype(odtype)
    f = plan_function[str(idtype)][str(odtype)]
    
    # handle the C2C cases (forward and reverse)
    if idtype.kind == odtype.kind:
        f.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, 
                      ctypes.c_int, ctypes.c_int]
        theplan = f(size, ip.ptr, op.ptr, direction, flags)
    # handle the R2C and C2R case
    else:
        f.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, 
                      ctypes.c_int]
        theplan = f(size, ip.ptr, op.ptr, flags)  
        
    return theplan
    
def execute(plan, invec, outvec):
    f = execute_function[str(invec.dtype)][str(outvec.dtype)]
    f.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    f(plan, invec.ptr, outvec.ptr)
    
def fft(invec, outvec, prec, itype, otype):
    theplan = plan(len(invec), invec.dtype, outvec.dtype, FFTW_FORWARD, get_measure_level())
    execute(theplan, invec, outvec)
    
def ifft(invec, outvec, prec, itype, otype):
    theplan = plan(len(invec), invec.dtype, outvec.dtype, FFTW_BACKWARD, get_measure_level())
    execute(theplan, invec, outvec)

    
    

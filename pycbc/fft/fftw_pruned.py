"""This module provides a functions to perform a pruned FFT based on FFTW

This should be considered a test and example module, as the functionality 
can and should be generalized to other FFT backends, and precisions.

These functions largely implemented the generic FFT decomposition as 
described rather nicely by wikipedia.

http://en.wikipedia.org/wiki/Cooley%E2%80%93Tukey_FFT_algorithm

I use a similar naming convention here, with minor simplifications to the 
twiddle factors. 
""" 
import numpy, scipy.weave, ctypes, pycbc.types
from pycbc.libutils import get_ctypes_library

# FFTW constants
FFTW_FORWARD = -1
FFTW_BACKWARD = 1
FFTW_MEASURE = 0
FFTW_PATIENT = 1 << 5
FFTW_ESTIMATE = 1 << 6
float_lib = get_ctypes_library('fftw3f', ['fftw3f'],mode=ctypes.RTLD_GLOBAL)
fexecute = float_lib.fftwf_execute_dft
fexecute.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]    

def plan_first_phase(N1, N2):
    N = N1*N2
    vin = pycbc.types.zeros(N, dtype=numpy.complex64)
    vout = pycbc.types.zeros(N, dtype=numpy.complex64)
    f = float_lib.fftwf_plan_many_dft
    f.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
                  ctypes.c_void_p, ctypes.c_void_p,
                  ctypes.c_int, ctypes.c_int,
                  ctypes.c_void_p, ctypes.c_void_p,
                  ctypes.c_int, ctypes.c_int,
                  ctypes.c_int, ctypes.c_int]   
    f.restype = ctypes.c_void_p
    return f(1, ctypes.byref(ctypes.c_int(N2)), N1,
             vin.ptr, None, N1, 1,
             vout.ptr, None, 1, N2, FFTW_BACKWARD, FFTW_MEASURE)  

_theplan = None
def first_phase(invec, outvec, N1, N2):
    """  This implements the first phase of the FFT decomposition, using
    the standard FFT many plans
    """
    global _theplan
    if _theplan is None:
        _theplan = plan_first_phase(N1, N2)
    fexecute(_theplan, invec.ptr, outvec.ptr)
    

def second_phase(invec, indices, N1, N2):
    """ This is the second phase of the FFT decomposition that actually performs
    the pruning. It is an explicit calculation for the subset of points. Note that
    there seem to be some numerical accumulation issues at various values of N1 and N2.
    
    Parameters
    ----------
    N1 : int
        The length of the second phase "FFT"
    N2 : int 
        The length of the first phase FFT
    indices : array of ints
        The index locations to calculate the FFT
    invec : 
        The result of the first phase FFT
        
    Returns
    -------
    out : array of floats
    """
    invec = numpy.array(invec.data, copy=False)
    NI = len(indices)
    N1=int(N1)
    N2=int(N2)
    out = numpy.zeros(len(indices), dtype=numpy.complex64)
    code = """
        float pi = 3.141592653;
        for(int i=0; i<NI; i++){
            std::complex<double> val= (0, 0);
            unsigned int k = indices[i];
            int N = N1*N2;
            float k2 = k % N2;
            float phase_inc = 2 * pi * float(k) / float(N);
            float sp, cp;

            for (float n1=0; n1<N1; n1+=1){
                sincosf(phase_inc * n1, &sp, &cp);
                val += std::complex<float>(cp, sp) * invec[int(k2 + N2*n1)];
            }
            out[i] = val;
        }
    """
    scipy.weave.inline(code, ['N1', 'N2', 'NI', 'indices', 'out', 'invec'])
    return out
    
def pruned_c2cifft(invec, outvec, indices):
    """Perform a pruned iFFT, only valid for power of 2 iffts as the
    decomposition is easier to choose. This is not a rict requirement of the
    functions, but it is unlikely to the optimal to use anything but power
     of 2.
    """
    # This is a sloppy guess at an OK decomposition boudary, but could be better
    # through benchmarking and optimization (the second phase is a lot slower
    # than it strictly has to be). 
    N2 = int(2 ** (numpy.log2( len(invec) ) / 2))
    N1 = len(invec)/N2

    # Do the explicit transpose here as I would like to move this out of the 
    # loop soon
    #invec = pycbc.types.Array(invec.data.copy().reshape(N2, N1).transpose().copy(), copy=False)
    first_phase(invec, outvec, N1=N1, N2=N2)
    return second_phase(outvec, indices, N1=N1, N2=N2)    

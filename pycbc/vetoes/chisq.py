# Copyright (C) 2012  Alex Nitz
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
from pycbc.types import Array, zeros, real_same_precision_as, TimeSeries, complex_same_precision_as, FrequencySeries
from pycbc.filter import sigmasq_series, make_frequency_series, sigmasq, matched_filter_core
import numpy
from pycbc.scheme import schemed
import pycbc.fft

BACKEND_PREFIX="pycbc.vetoes.chisq_"

def power_chisq_bins_from_sigmasq_series(sigmasq_series, num_bins, kmin, kmax):
    """Returns bins of equal power for use with the chisq functions
    
    Parameters
    ----------
    
    sigmasq_series: FrequencySeries
        A frequency series containing the cumulative power of a filter template
        preweighted by a psd.
    num_bins: int
        The number of chisq bins to calculate.
    kmin: int
    kmax: int    
        
    Returns
    -------
    
    bins: List of ints
        A list of the edges of the chisq bins is returned. 
    
    """
    sigmasq = sigmasq_series[kmax - 1]                        
    edge_vec = numpy.arange(0, num_bins) * sigmasq / num_bins
    bins = numpy.searchsorted(sigmasq_series[kmin:kmax], edge_vec, side='right')
    bins += kmin
    return numpy.append(bins, kmax)

def power_chisq_bins(htilde, num_bins, psd, low_frequency_cutoff=None, 
                     high_frequency_cutoff=None):
    """Returns bins of equal power for use with the chisq functions
    
    Parameters
    ----------
    
    htilde: FrequencySeries
        A frequency series containing the template waveform
    num_bins: int
        The number of chisq bins to calculate.
    psd: FrequencySeries
        A frequency series containing the psd. Its length must be commensurate
        with the template waveform.
    low_frequency_cutoff: {None, float}, optional
        The low frequency cutoff to apply
    high_frequency_cutoff: {None, float}, optional
        The high frequency cutoff to apply
    
    Returns
    -------
    
    bins: List of ints
        A list of the edges of the chisq bins is returned. 
    """
    sigma_vec = sigmasq_series(htilde, psd, low_frequency_cutoff, 
                               high_frequency_cutoff).numpy() 
    kmin = int(low_frequency_cutoff / htilde.delta_f)
    kmax = len(sigma_vec)
    return power_chisq_bins_from_sigmasq_series(sigma_vec, num_bins, kmin, kmax)
    
@schemed(BACKEND_PREFIX)
def chisq_accum_bin(chisq, q):
    pass
    
def shift_sum(v1, shifts, slen=None, offset=0):
    """ Calculate the time shifted sum of the FrequencySeries
    """
    from scipy.weave import inline
    v1 = v1.data
    shifts = numpy.array(shifts, dtype=numpy.float32)
    vlen = len(v1)
    if slen is None:
        slen = vlen
        
    code = """
        float t1, t2;         
        
        for (int j=0; j<vlen; j++){
            std::complex<float> v = v1[j];
            float vr = v.real();
            float vi = v.imag();  
                       
            for (int i=0; i<n; i++){
                outr[i] += vr * pr[i] - vi * pi[i];
                outi[i] += vr * pi[i] + vi * pr[i];
                t1 = pr[i];
                t2 = pi[i];
                pr[i] = t1 * vsr[i] - t2 * vsi[i];
                pi[i] = t1 * vsi[i] + t2 * vsr[i]; 
            }                                              
        }            
    """
    n = int(len(shifts))
    
    #Calculate the incremental rotation for each time shift
    vs = numpy.exp(numpy.pi * 2j * shifts / slen )
    vsr = vs.real*1
    vsi = vs.imag*1
    
    # Create some output memory
    outr =  numpy.zeros(n, dtype=numpy.float32)
    outi =  numpy.zeros(n, dtype=numpy.float32)
    
    # Create memory for storing the cumulative rotation for each time shift
    p = numpy.exp(numpy.pi * 2j *  offset * shifts / slen)
    pi = numpy.zeros(n, dtype=numpy.float32) + p.imag
    pr = numpy.zeros(n, dtype=numpy.float32) + p.real

    inline(code, ['v1', 'n', 'vlen', 'pr', 'pi', 'outi', 'outr', 'vsr', 'vsi'], )
    return  Array(outr + 1.0j * outi, dtype=numpy.complex64)
    
def power_chisq_at_points_from_precomputed(corr, snr, h_norm, bins, indices):
    """Calculate the chisq timeseries from precomputed values for only select
    points.
    
    Parameters
    ----------
    
    corr: FrequencySeries
        The product of the template and data in the frequency domain.
    snr: Array
        The normalized array of snr values at only the selected points in `indices`.
    h_norm: float
        The sigmasq of the template
    bins: List of integers
        The edges of the equal power bins
    indices: Array
        The indices where we will calculate the chisq. These must be relative 
        to the given `corr` series.           
    
    Returns
    -------
    chisq: Array
        An array containing only the chisq at the selected points.
    """
    snr = Array(snr, copy=False)
    
    chisq = zeros(len(indices), dtype=real_same_precision_as(corr))     
    num_bins = len(bins) - 1
    
    norm = 4 * corr.delta_f / numpy.sqrt(h_norm)
    
    for j in range(len(bins)-1):
        k_min = int(bins[j])
        k_max = int(bins[j+1])    
             
        qi = shift_sum(corr[k_min:k_max], indices, slen=len(corr), offset=k_min) * norm
        chisq += qi.squared_norm()  
        
    return (chisq * num_bins - snr.squared_norm())
    
def power_chisq_from_precomputed(corr, snr, bins, snr_norm):
    """Calculate the chisq timeseries from precomputed values
    
    Parameters
    ----------
    
    corr: FrequencySeries
        The produce of the template and data in the frequency domain.
    snr: TimeSeries
        The unnormalized snr time series.
    bins: List of integers
        The edges of the chisq bins.
    snr_norm:
        The snr normalization factor. (true snr = snr * snr_norm)
    
    
    Returns
    -------
    chisq: TimeSeries
    """
       
    q = zeros(len(snr), dtype=complex_same_precision_as(snr))
    qtilde = zeros(len(snr), dtype=complex_same_precision_as(snr))
    chisq = TimeSeries(zeros(len(snr), dtype=real_same_precision_as(snr)), 
                       delta_t=snr.delta_t, epoch=snr.start_time, copy=False)
    
    chisq_norm = snr_norm ** 2.0
    num_bins = len(bins) - 1
    
    for j in range(len(bins)-1): 
        k_min = int(bins[j])
        k_max = int(bins[j+1])
        
        qtilde[k_min:k_max] = corr[k_min:k_max]
        pycbc.fft.ifft(qtilde, q) 
        qtilde[k_min:k_max].clear()
        chisq_accum_bin(chisq, q)
        
    return (chisq * num_bins - snr.squared_norm()) * chisq_norm

def power_chisq(template, data, num_bins, psd, low_frequency_cutoff=None, high_frequency_cutoff=None):
    """Calculate the chisq timeseries 

    Parameters
    ----------
    template: FrequencySeries or TimeSeries
        A time or frequency series that contains the filter template. The length
        must be commensurate with the data. 
    data: FrequencySeries or TimeSeries
        A time ore frequency series that contains the data to filter. The length
        must be commensurate with the template.
    num_bins: int
        The number of bins in the chisq. Note that the dof goes as 2*num_bin-2. 
    psd: FrequencySeries
        The psd of the data. 
    low_frequency_cutoff: {None, float}, optional
        The low frequency cutoff to apply.
    high_frequency_cutoff: {None, float}, optional
        The high frequency cutoff to apply. 

    Returns
    -------
    chisq: TimeSeries
        TimeSeries containing the chisq values for all times. 
    """
    htilde = make_frequency_series(template)
    stilde = make_frequency_series(data)
    
    bins = power_chisq_bins(htilde, num_bins, psd, low_frequency_cutoff, high_frequency_cutoff)
    
    corra = zeros((len(htilde)-1)*2, dtype=htilde.dtype)
    
    total_snr, corr, tnorm = matched_filter_core(htilde, stilde, psd,
                           low_frequency_cutoff, high_frequency_cutoff, corr_out=corra)

    return power_chisq_from_precomputed(corr, total_snr, bins, tnorm)

    
                
        



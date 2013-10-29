# Copyright (C) 2013  Alex Nitz
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
"""
These are simple unit tests for lalsimulation
"""
import sys
import pycbc
import unittest
from pycbc.types import *
from pycbc.scheme import *
from pycbc.filter import *
from pycbc.waveform import *
import pycbc.fft
import matplotlib
matplotlib.use('Agg')
import pylab
import numpy
import lal, lalsimulation
import copy

from utils import parse_args_cpu_only, simple_exit
matplotlib.rc('text', usetex=True)
parse_args_cpu_only("Lalsimulation Waveforms")

class TestLALSimulation(unittest.TestCase):
    def setUp(self,*args):
        self.save_plots = True
        self.show_plots = False
        self.plot_dir = "plots/"
        
        class params(object):
            pass
        self.p = params()
        
        self.p.mass1 = 10
        self.p.mass2 = 10
        self.p.spin1x = 0
        self.p.spin1y = 0
        self.p.spin1z = 0
        self.p.spin2x = 0
        self.p.spin2y = 0
        self.p.spin2z = 0
        self.p.inclination = 0
        self.p.coa_phase = 0
        self.p.delta_t=1.0/4096
        self.p.f_lower=30
        self.p.approximant= self.kwds['approximant']
        
        from pycbc import version
        self.version_txt = "pycbc: %s  %s\n" % (version.git_hash, version.date) + \
                           "lalsimulation: %s  %s" % (lalsimulation.lalSimulationVCSId, lalsimulation.lalSimulationVCSDate)
        
    def test_orbital_phase(self):
        #""" Check that the waveform is consistent under phase changes
        #"""
        mass1 = 10 
        mass2 = 10
        
        pylab.figure()
        pylab.axes([.1, .2, 0.8, 0.70])
        hp_ref, hc_ref = get_td_waveform(self.p, coa_phase=0)
        pylab.plot(hp_ref.sample_times, hp_ref, label="phiref")
       
        hp, hc = get_td_waveform(self.p, coa_phase=lal.LAL_PI/4)
        m, i = match(hp_ref, hp)
        self.assertAlmostEqual(1, m, places=2)
        o = overlap(hp_ref, hp)
        pylab.plot(hp.sample_times, hp, label="phiref \pi/4")
        
        hp, hc = get_td_waveform(self.p, coa_phase=lal.LAL_PI/2)
        m, i = match(hp_ref, hp)
        o = overlap(hp_ref, hp)
        self.assertAlmostEqual(1, m, places=7)
        self.assertAlmostEqual(-1, o, places=7)
        pylab.plot(hp.sample_times, hp, label="phiref \pi/2")
        
        hp, hc = get_td_waveform(self.p, coa_phase=lal.LAL_PI)
        m, i = match(hp_ref, hp)
        o = overlap(hp_ref, hp)
        self.assertAlmostEqual(1, m, places=7)
        self.assertAlmostEqual(1, o, places=7)
        pylab.plot(hp.sample_times, hp, label="phiref \pi")                         
        
        pylab.xlim(-0.05, float(hp.end_time))
        pylab.title("Vary %s oribital phiref, h+" % self.p.approximant)
        pylab.xlabel("Time to coalescence (s)")
        pylab.ylabel("GW Strain")
        pylab.legend(loc="upper left")
        
        info = self.version_txt
        pylab.figtext(0, 0, info)
        
        if self.show_plots:
            pylab.show()
            
        if self.save_plots:
            pname = self.plot_dir + "/%s-vary-phase.png" % self.p.approximant
            pylab.savefig(pname)
        
    def test_distance_scale(self):   
        #""" Check that the waveform is consistent under distance changes
        #"""     
        distance = 1e6
        tolerance = 1e-5
        fac = 10
    
        hpc, hcc = get_td_waveform(self.p, distance=distance)
        hpm, hcm = get_td_waveform(self.p, distance=distance*fac)
        hpf, hcf = get_td_waveform(self.p, distance=distance*fac*fac)
        hpn, hcn = get_td_waveform(self.p, distance=distance/fac)
        
        pylab.figure()
        pylab.axes([.1, .2, 0.8, 0.70])
        htilde = make_frequency_series(hpc)
        pylab.loglog(htilde.sample_frequencies, abs(htilde), label="D")
        
        htilde = make_frequency_series(hpm)
        pylab.loglog(htilde.sample_frequencies, abs(htilde), label="D * %s" %fac)
       
        htilde = make_frequency_series(hpf)
        pylab.loglog(htilde.sample_frequencies, abs(htilde), label="D * %s" %(fac*fac))
        
        htilde = make_frequency_series(hpn)
        pylab.loglog(htilde.sample_frequencies, abs(htilde), label="D / %s" %fac)
            
        pylab.title("Vary %s distance, $\\tilde{h}$+" % self.p.approximant)
        pylab.xlabel("GW Frequency (Hz)")
        pylab.ylabel("GW Strain")
        pylab.legend()
        
        info = self.version_txt
        pylab.figtext(0, 0, info)
        
        if self.show_plots:
            pylab.show()
            
        if self.save_plots:
            pname = self.plot_dir + "/%s-distance-scaling.png" % self.p.approximant
            pylab.savefig(pname)
            
        self.assertTrue(hpc.almost_equal_elem(hpm * fac, tolerance, relative=True))
        self.assertTrue(hpc.almost_equal_elem(hpf * fac * fac, tolerance, relative=True))
        self.assertTrue(hpc.almost_equal_elem(hpn / fac, tolerance, relative=True))
            
    def test_param_jitter(self):
        #""" Check that the overlaps are consistent for nearby waveforms
        #"""
        def nearby(params):
            tol = 1e-7
            
            from numpy.random import uniform
            nearby_params = copy.copy(params)
            nearby_params.mass1 *= uniform(low=1-tol, high=1+tol)
            nearby_params.mass2 *= uniform(low=1-tol, high=1+tol)
            nearby_params.spin1x *= uniform(low=1-tol, high=1+tol)
            nearby_params.spin1y *= uniform(low=1-tol, high=1+tol)
            nearby_params.spin1z *= uniform(low=1-tol, high=1+tol)
            nearby_params.spin2x *= uniform(low=1-tol, high=1+tol)
            nearby_params.spin2y *= uniform(low=1-tol, high=1+tol)
            nearby_params.spin2z *= uniform(low=1-tol, high=1+tol)
            nearby_params.inclination *= uniform(low=1-tol, high=1+tol)
            nearby_params.coa_phase *= uniform(low=1-tol, high=1+tol)
            return nearby_params
            
        hp, hc = get_td_waveform(self.p)    
        
        for i in range(10):
            p_near = nearby(self.p)
            hpn, hcn = get_td_waveform(p_near)
            
            maxlen = max(len(hpn), len(hp))
            hp.resize(maxlen)
            hpn.resize(maxlen)
            o = overlap(hp, hpn)
            self.assertAlmostEqual(1, o, places=5)
            
    #def test_inclination(self):
    #    """ Test that the waveform is consistent for changes in inclination
    #    """
    #    pass
        
    #def test_ref_freq(self):
    #    """ Test that the waveform is consistent for changes in the reference
    #    frequency
    #    """
    #    pass
        
    #def test_stability(self):
    #    """ Test that the waveform is robust against changing the intitial
    #    frequency
    #    """
    #    pass
    
def test_maker(class_name, name, **kwds):
    class Test(class_name):
        def __init__(self, *args):
            self.kwds = kwds
            class_name.__init__(self, *args)
        
    Test.__name__ = "Test %s" % name    
    return Test
 
suite = unittest.TestSuite()   
for apx in td_approximants():
    # The inspiral wrapper is only single precision we won't bother checking
    # it here. It may need different tolerances and some special care.
    if apx.startswith("Inspiral-"):
        continue
    vars()[apx] = test_maker(TestLALSimulation, apx, approximant=apx)
    suite.addTest( unittest.TestLoader().loadTestsFromTestCase(vars()[apx]) )

if __name__ == '__main__':
    results = unittest.TextTestRunner(verbosity=2).run(suite)
    simple_exit(results)

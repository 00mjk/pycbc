# Copyright (C) 2013 Ian Harry
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
These are the unittests for the pycbc.tmpltbank module
"""

import os
import numpy
import pycbc.tmpltbank
import pycbc.psd
import pycbc.pnutils
from pycbc.types import Array
import difflib
import sys

import unittest
from utils import parse_args_cpu_only, simple_exit

# This will return whatever is appropriate, depending on whether this
# particular instance of the unittest was called for CPU, CUDA, or OpenCL
parse_args_cpu_only("Template bank module")

class TmpltbankTestClass(unittest.TestCase):
    def setUp(self):
        # Where are my data files?
        if os.path.isfile('test/data/ZERO_DET_high_P.txt'):
            self.dataDir = 'test/data/'
        elif os.path.isfile('data/ZERO_DET_high_P.txt'):
            self.dataDir = 'data/'
        else:
            self.assertTrue(False, msg="Cannot find data files!")

        self.deltaF = 0.1
        self.f_low = 15
        self.f_upper = 2000
        self.f0 = 70
        self.sampleRate = 4096
        self.pnOrder = 'taylorF4_45PN'
        self.minMass1 = 1
        self.minMass2 = 1
        self.maxMass1 = 5
        self.maxMass2 = 5
        self.maxNSSpinMag = 0.5
        self.maxBHSpinMag = 0.9
        self.minTotalMass = 2.5
        self.maxTotalMass = 6.0
        # Need to use F2 metric for ethinca
        self.ethincaOrder = 'threePointFivePN'
        self.ethincaCutoff = 'SchwarzISCO'
        self.ethincaFreqStep = 10.

        self.segLen = 1./self.deltaF
        self.psdSize = int(self.segLen * self.sampleRate) / 2. + 1

        self.psd = pycbc.psd.from_txt('%sZERO_DET_high_P.txt' %(self.dataDir),\
                self.psdSize, self.deltaF, self.f_low, is_asd_file=True)

        metricParams = pycbc.tmpltbank.metricParameters(self.pnOrder,\
                         self.f_low, self.f_upper, self.deltaF, self.f0)
        metricParams.psd = self.psd
        
        massRangeParams = pycbc.tmpltbank.massRangeParameters(self.minMass1,\
                            self.maxMass1, self.minMass2, self.maxMass2,\
                            maxNSSpinMag=self.maxNSSpinMag,\
                            maxBHSpinMag=self.maxBHSpinMag,\
                            maxTotMass=self.maxTotalMass,\
                            minTotMass=self.minTotalMass) 

        metricParams = pycbc.tmpltbank.determine_eigen_directions(metricParams)

        vals=pycbc.tmpltbank.estimate_mass_range(10, massRangeParams,\
               metricParams, self.f_upper, covary=False)

        cov = numpy.cov(vals)
        _,self.evecsCV = numpy.linalg.eig(cov)
        metricParams.evecsCV = {}
        metricParams.evecsCV[self.f_upper] = self.evecsCV

        vals=pycbc.tmpltbank.estimate_mass_range(100000, massRangeParams,\
               metricParams, self.f_upper, covary=False)

        self.metricParams = metricParams
        self.massRangeParams = massRangeParams
        self.ethincaParams = pycbc.tmpltbank.ethincaParameters(
            self.ethincaOrder, self.ethincaCutoff, self.ethincaFreqStep,
            doEthinca=True)

        self.xis = vals

    def test_eigen_directions(self):
        evalsStock = Array(numpy.loadtxt('%sstockEvals.dat'%(self.dataDir)))
        evecsStock = Array(numpy.loadtxt('%sstockEvecs.dat'%(self.dataDir)))
        maxEval = max(evalsStock)
        evalsCurr = Array(self.metricParams.evals[self.f_upper])
        evecsCurr = Array(self.metricParams.evecs[self.f_upper])
        errMsg = "pycbc.tmpltbank.determine_eigen_directions has failed "
        errMsg += "sanity check."
        evalsDiff = abs(evalsCurr - evalsStock)/maxEval
        self.assertTrue(not (evalsDiff.data > 1E-5).any(), msg=errMsg)
        for stock,test in zip(evecsStock.data,evecsCurr.data):
            stockScaled = stock * evalsCurr.data**0.5
            testScaled = test * evalsCurr.data**0.5
            diff = stockScaled - testScaled
            self.assertTrue(not (diff > 1E-4).any(), msg=errMsg)

    def test_get_random_mass(self):
       mass,eta,beta,sigma,gamma,spin1z,spin2z = \
             pycbc.tmpltbank.get_random_mass(1000000, self.massRangeParams)
       errMsg = "pycbc.tmpltbank.get_random_mass returns invalid ranges."
       self.assertTrue(not (mass < 2.5).any(),msg=errMsg)
       self.assertTrue(not (mass > 6.0).any(),msg=errMsg)
       # Get individual masses
       diff = (mass*mass * (1-4*eta))**0.5
       mass1 = (mass + diff)/2.
       mass2 = (mass - diff)/2.
       self.assertTrue(not (mass1 > 5 * 1.001).any(),msg=errMsg)
       self.assertTrue(not (mass1 < 1 * 0.999).any(),msg=errMsg)
       self.assertTrue(not (mass2 > 5 * 1.001).any(),msg=errMsg)
       self.assertTrue(not (mass2 < 1 * 0.999).any(),msg=errMsg)
       self.assertTrue(not (mass1 < mass2).any(),msg=errMsg)
       nsSpin1 = spin1z[mass1 < 3.0]
       nsSpin2 = spin2z[mass2 < 3.0]
       bhSpin1 = spin1z[mass1 > 3.0]
       bhSpin2 = spin2z[mass2 > 3.0]
       self.assertTrue(not (abs(nsSpin1) > 0.5).any(), msg=errMsg)
       self.assertTrue(not (abs(nsSpin2) > 0.5).any(), msg=errMsg) 
       self.assertTrue(not (abs(bhSpin1) > 0.9).any(), msg=errMsg)
       self.assertTrue(not (abs(bhSpin2) > 0.9).any(), msg=errMsg)

    def test_chirp_params(self):
        chirps=pycbc.tmpltbank.get_chirp_params(4, 0.24 ,0.2 ,0.2 ,0.2 ,0.1, \
                              self.metricParams.f0, self.metricParams.pnOrder)
        stockChirps = numpy.loadtxt('%sstockChirps.dat'%(self.dataDir))
        diff = (chirps - stockChirps) / stockChirps
        errMsg = "Calculated chirp params differ from that expected."
        self.assertTrue( not (diff > 1E-4).any(), msg=errMsg)

    def test_hexagonal_placement(self):
        arrz = pycbc.tmpltbank.generate_hexagonal_lattice(10, 0, 10, 0, 0.03)
        arrz = numpy.array(arrz)
        stockGrid = numpy.loadtxt("%sstockHexagonal.dat"%(self.dataDir))
        diff = arrz - stockGrid
        errMsg = "Calculated lattice differs from that expected."
        self.assertTrue( not (diff > 1E-4).any(), msg=errMsg)

    def test_anstar_placement(self):
        arrz = pycbc.tmpltbank.generate_anstar_3d_lattice(0, 10, 0, 10, 0, \
                                                          10, 0.03)
        arrz = numpy.array(arrz)
        stockGrid = numpy.loadtxt("%sstockAnstar3D.dat"%(self.dataDir))
        diff = arrz - stockGrid
        errMsg = "Calculated lattice differs from that expected."
        self.assertTrue( not (diff > 1E-4).any(), msg=errMsg)

    def test_get_mass_distribution(self):
        # Just run the function, no checking output
        pycbc.tmpltbank.get_mass_distribution([1.35,0.25,0.4,-0.2], 2, \
                          self.massRangeParams, self.metricParams, \
                          self.f_upper, \
                          numJumpPoints=123, chirpMassJumpFac=0.0002, \
                          etaJumpFac=0.009, spin1zJumpFac=0.1, \
                          spin2zJumpFac=0.2)

    def test_get_phys_cov_masses(self):
        evecs = self.metricParams.evecs[self.f_upper]
        evals = self.metricParams.evals[self.f_upper]
        masses1 = [4,0.25,0.4,0.3]
        masses2 = [4.01,0.249,0.41,0.29]
        spinSet1 = pycbc.pnutils.get_beta_sigma_from_aligned_spins(\
                     masses1[1], masses1[2], masses1[3])
        spinSet2 = pycbc.pnutils.get_beta_sigma_from_aligned_spins(\
                     masses2[1], masses2[2], masses2[3])
        xis1 = pycbc.tmpltbank.get_cov_params(masses1[0], masses1[1], \
                 spinSet1[0], spinSet1[1], spinSet1[2], spinSet1[3], \
                 self.metricParams, self.f_upper)
        xis2 = pycbc.tmpltbank.get_cov_params(masses2[0], masses2[1], \
                 spinSet2[0], spinSet2[1], spinSet2[2], spinSet2[3], \
                 self.metricParams, self.f_upper)

        testXis = [xis1[0],xis1[1]]
        bestMasses = masses2
        bestXis = xis2
        output = pycbc.tmpltbank.get_physical_covaried_masses(testXis, \
                   bestMasses, bestXis, 0.0001, self.massRangeParams, \
                   self.metricParams, self.f_upper)
        # Test that returned xis are close enough
        diff = (output[6][0] - testXis[0])**2
        diff += (output[6][1] - testXis[1])**2
        errMsg = 'pycbc.tmpltbank.get_physical_covaried_masses '
        errMsg += 'failed to find a point within the desired limits.'
        self.assertTrue( diff < 1E-4,msg=errMsg)
        # Test that returned masses and xis agree
        massT = output[0] + output[1]
        etaT = output[0]*output[1] / (massT*massT)
        spinSetT = pycbc.pnutils.get_beta_sigma_from_aligned_spins(\
                     etaT, output[2], output[3])
        xisT = pycbc.tmpltbank.get_cov_params(massT, etaT, \
                 spinSetT[0], spinSetT[1], spinSetT[2], spinSetT[3], \
                 self.metricParams, self.f_upper)
        errMsg = "Recovered xis do not agree with those expected."
        self.assertTrue( abs(xisT[0] - output[6][0]) < 1E-5, msg=errMsg)
        self.assertTrue( abs(xisT[1] - output[6][1]) < 1E-5, msg=errMsg)
        self.assertTrue( abs(xisT[2] - output[6][2]) < 1E-5, msg=errMsg)
        self.assertTrue( abs(xisT[3] - output[6][3]) < 1E-5, msg=errMsg)

    def test_stack_xi_direction(self):
        # Just run the function, no checking output
        evecs = self.metricParams.evecs[self.f_upper]
        evals = self.metricParams.evals[self.f_upper]
        masses1 = [4,0.25,0.4,0.3]
        masses2 = [4.01,0.249,0.41,0.29]
        spinSet1 = pycbc.pnutils.get_beta_sigma_from_aligned_spins(\
                     masses1[1], masses1[2], masses1[3])
        spinSet2 = pycbc.pnutils.get_beta_sigma_from_aligned_spins(\
                     masses2[1], masses2[2], masses2[3])
        xis1 = pycbc.tmpltbank.get_cov_params(masses1[0], masses1[1], \
                 spinSet1[0], spinSet1[1], spinSet1[2], spinSet1[3], \
                 self.metricParams, self.f_upper)
        xis2 = pycbc.tmpltbank.get_cov_params(masses2[0], masses2[1], \
                 spinSet2[0], spinSet2[1], spinSet2[2], spinSet2[3], \
                 self.metricParams, self.f_upper)
        testXis = [xis1[0],xis1[1]]
        bestMasses = masses2
        bestXis = xis2

        depths = pycbc.tmpltbank.stack_xi_direction_brute(testXis, \
              bestMasses, bestXis, 3, 0.03, self.massRangeParams, \
              self.metricParams, self.f_upper, numIterations=50)

    def test_point_distance(self):
        masses1 = [2,2,0.4,0.6]
        masses2 = [2.02,1.97,0.41,0.59]
        dist, xis1, xis2 = pycbc.tmpltbank.get_point_distance(masses1, \
                             masses2, self.metricParams, self.f_upper)
        diff = abs((dist - 23.4019262742) / dist)
  
        errMsg = "Obtained distance does not agree with expected value."
        self.assertTrue( diff < 1E-5, msg=errMsg)

    def test_conv_to_sngl(self):
        # Just run the function, no checking output
        masses1 = [(2,2,0.4,0.3),(4.01,0.249,0.41,0.29)]
        pycbc.tmpltbank.convert_to_sngl_inspiral_table(masses1, "a")

    def test_ethinca_calc(self):
        # Just run the function, no checking output
        m1 = 2.
        m2 = 2.
        s1z = 0.
        s2z = 0.
        # ethinca calc breaks unless f0 = fLow
        self.metricParams.f0 = self.metricParams.fLow
        output = pycbc.tmpltbank.calculate_ethinca_metric_comps(
            self.metricParams, self.ethincaParams, m1, m2, s1z, s2z)
        print output
        # restore initial f0 value
        self.metricParams.f0 = self.f0

    def tearDown(self):
        pass

suite = unittest.TestSuite()
suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TmpltbankTestClass))
 
if  __name__ == '__main__':
    results = unittest.TextTestRunner(verbosity=2).run(suite)
    simple_exit(results)


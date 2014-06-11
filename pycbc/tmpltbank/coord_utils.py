# Copyright (C) 2013 Ian W. Harry
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

from __future__ import division
import numpy
from lal import LAL_PI, LAL_MTSUN_SI
from pycbc.tmpltbank.lambda_mapping import get_chirp_params
from pycbc import pnutils

def estimate_mass_range(numPoints, massRangeParams, metricParams, fUpper,\
                        covary=True):
    """
    This function will generate a large set of points with random masses and
    spins (using pycbc.tmpltbank.get_random_mass) and translate these points
    into the xi_i coordinate system for the given upper frequency cutoff.

    Parameters
    ----------
    numPoints : int
        Number of systems to simulate
    massRangeParams : massRangeParameters instance
        Instance holding all the details of mass ranges and spin ranges.
    metricParams : metricParameters instance
        Structure holding all the options for construction of the metric
        and the eigenvalues, eigenvectors and covariance matrix
        needed to manipulate the space.
    fUpper : float
        The value of fUpper to use when getting the mu coordinates from the
        lambda coordinates. This must be a key in metricParams.evals and
        metricParams.evecs (ie. we must know how to do the transformation for
        the given value of fUpper). It also must be a key in
        metricParams.evecsCV if covary=True.
    covary : boolean, optional (default = True)
        If this is given then evecsCV will be used to rotate from the Cartesian
        coordinate system into the principal coordinate direction (xi_i). If
        not given then points in the original Cartesian coordinates are
        returned.


    Returns
    -------
    xis : numpy.array
        A list of the positions of each point in the xi_i coordinate system.
    """
    valsF = get_random_mass(numPoints, massRangeParams)
    mass = valsF[0]
    eta = valsF[1]
    beta = valsF[2]
    sigma = valsF[3]
    gamma = valsF[4]
    chis = 0.5*(valsF[5] + valsF[6])
    if covary:
        lambdas = get_cov_params(mass, eta, beta, sigma, gamma, chis, \
                                 metricParams, fUpper)
    else:
        lambdas = get_conv_params(mass, eta, beta, sigma, gamma, chis, \
                                  metricParams, fUpper)

    return numpy.array(lambdas)

def get_random_mass(numPoints, massRangeParams):
    """
    This function will generate a large set of points within the chosen mass
    and spin space. It will also return the corresponding PN spin coefficients
    for ease of use later (though these may be removed at some future point).

    Parameters
    ----------
    numPoints : int
        Number of systems to simulate
    massRangeParams : massRangeParameters instance
        Instance holding all the details of mass ranges and spin ranges.

    Returns
    --------
    mass : numpy.array
        List of the total masses.
    eta : numpy.array
        List of the symmetric mass ratios
    beta : numpy.array
        List of the 1.5PN beta spin coefficients
    sigma : numpy.array
        List of the 2PN sigma spin coefficients
    gamma : numpy.array
        List of the 2.5PN gamma spin coefficients
    spin1z : numpy.array
        List of the spin on the heavier body. NOTE: Body 1 is **always** the
        heavier body to remove mass,eta -> m1,m2 degeneracy
    spin2z : numpy.array
        List of the spin on the smaller body. NOTE: Body 2 is **always** the
        smaller body to remove mass,eta -> m1,m2 degeneracy
    """

    # WARNING: We expect mass1 > mass2 ALWAYS

    # First we choose the total masses from a unifrom distribution in mass
    # to the -5/3. power.
    mass = numpy.random.random(numPoints) * \
           (massRangeParams.minTotMass**(-5./3.) \
            - massRangeParams.maxTotMass**(-5./3.)) \
           + massRangeParams.maxTotMass**(-5./3.)
    mass = mass**(-3./5.)

    # Next we choose the mass ratios, this will take different limits based on
    # the value of total mass
    maxmass2 = numpy.minimum(mass/2., massRangeParams.maxMass2)
    minmass1 = numpy.maximum(massRangeParams.minMass1, mass/2.)
    mineta = numpy.maximum(massRangeParams.minCompMass \
                            * (mass-massRangeParams.minCompMass)/(mass*mass), \
                           massRangeParams.maxCompMass \
                            * (mass-massRangeParams.maxCompMass)/(mass*mass))
    # Note that mineta is a numpy.array because mineta depends on the chirp
    # mass. Therefore this is not precomputed in the massRangeParams instance
    if massRangeParams.minEta:
        mineta = numpy.maximum(massRangeParams.minEta, mineta)
    maxeta = numpy.minimum(massRangeParams.maxEta, maxmass2 \
                             * (mass - maxmass2) / (mass*mass))
    maxeta = numpy.minimum(maxeta, minmass1 \
                             * (mass - minmass1) / (mass*mass))
    if (maxeta < mineta).any():
        errMsg = "ERROR: Maximum eta is smaller than minimum eta!!"
        print maxeta
        print mineta
        raise ValueError(errMsg)
    eta = numpy.random.random(numPoints) * (maxeta - mineta) + mineta

    # Also calculate the component masses; mass1 > mass2
    diff = (mass*mass * (1-4*eta))**0.5
    mass1 = (mass + diff)/2.
    mass2 = (mass - diff)/2.
    # Check the masses are where we want them to be (allowing some floating
    # point rounding error).
    if (mass1 > massRangeParams.maxMass1*1.001).any() \
          or (mass1 < massRangeParams.minMass1*0.999).any():
        errMsg = "Mass1 is not within the specified mass range."
        raise ValueError(errMsg)
    if (mass2 > massRangeParams.maxMass2*1.001).any() \
          or (mass2 < massRangeParams.minMass2*0.999).any():
        errMsg = "Mass2 is not within the specified mass range."
        raise ValueError(errMsg)

    # Next up is the spins. First check if we have non-zero spins
    if massRangeParams.maxNSSpinMag == 0 and massRangeParams.maxBHSpinMag == 0:
        spinspin = numpy.zeros(numPoints,dtype=float)
        spin1z = numpy.zeros(numPoints,dtype=float)
        spin2z = numpy.zeros(numPoints,dtype=float)
        beta = numpy.zeros(numPoints,dtype=float)
        sigma = numpy.zeros(numPoints,dtype=float)
        gamma = numpy.zeros(numPoints,dtype=float)
        spin1z = numpy.zeros(numPoints,dtype=float)
        spin2z = numpy.zeros(numPoints,dtype=float)
    else:
        # Spin 1 first
        mspin = numpy.zeros(len(mass1))
        mspin += massRangeParams.maxNSSpinMag
        mspin[mass1 > 3] = massRangeParams.maxBHSpinMag
        spin1z = (2*numpy.random.random(numPoints) - 1) * mspin
        # Then spin 2
        mspin = numpy.zeros(len(mass2))
        mspin += massRangeParams.maxNSSpinMag
        mspin[mass2 > 3] = massRangeParams.maxBHSpinMag
        spin2z = (2*numpy.random.random(numPoints) - 1) * mspin
        spinspin = spin1z*spin2z

        # And compute the PN components that come out of this
        beta, sigma, gamma, chiS = pnutils.get_beta_sigma_from_aligned_spins(
            eta, spin1z, spin2z)

    return mass,eta,beta,sigma,gamma,spin1z,spin2z

def get_cov_params(totmass, eta, beta, sigma, gamma, chis, metricParams, \
                   fUpper):
    """
    Function to convert between masses and spins and locations in the xi
    parameter space. Xi = Cartesian metric and rotated to principal components.

    Parameters
    -----------
    totmass : float or numpy.array
        Total mass(es) of the system(s)
    eta : float or numpy.array
        Symmetric mass ratio(s) of the system(s)
    beta : float or numpy.array
        1.5PN spin coefficient(s) of the system(s)
    sigma: float or numpy.array
        2PN spin coefficient(s) of the system(s)
    gamma : float or numpy.array
        2.5PN spin coefficient(s) of the system(s)
    chis : float or numpy.array
        0.5 * (spin1z + spin2z) for the system(s)
    metricParams : metricParameters instance
        Structure holding all the options for construction of the metric
        and the eigenvalues, eigenvectors and covariance matrix
        needed to manipulate the space.
    fUpper : float
        The value of fUpper to use when getting the mu coordinates from the
        lambda coordinates. This must be a key in metricParams.evals,
        metricParams.evecs and metricParams.evecsCV
        (ie. we must know how to do the transformation for
        the given value of fUpper)

    Returns
    --------
    xis : list of floats or numpy.arrays
        Position of the system(s) in the xi coordinate system
    """

    # Do this by doing masses - > lambdas -> mus
    mus = get_conv_params(totmass, eta, beta, sigma, gamma, chis, \
                          metricParams, fUpper)
    # and then mus -> xis
    xis = get_covaried_params(mus, metricParams.evecsCV[fUpper])
    return xis

def get_conv_params(totmass, eta, beta, sigma, gamma, chis, metricParams, \
                    fUpper):
    """
    Function to convert between masses and spins and locations in the mu
    parameter space. Mu = Cartesian metric, but not principal components.

    Parameters
    -----------
    totmass : float or numpy.array
        Total mass(es) of the system(s)
    eta : float or numpy.array
        Symmetric mass ratio(s) of the system(s)
    beta : float or numpy.array
        1.5PN spin coefficient(s) of the system(s)
    sigma: float or numpy.array
        2PN spin coefficient(s) of the system(s)
    gamma : float or numpy.array
        2.5PN spin coefficient(s) of the system(s)
    chis : float or numpy.array
        0.5 * (spin1z + spin2z) for the system(s)
    metricParams : metricParameters instance
        Structure holding all the options for construction of the metric
        and the eigenvalues, eigenvectors and covariance matrix
        needed to manipulate the space.
    fUpper : float
        The value of fUpper to use when getting the mu coordinates from the
        lambda coordinates. This must be a key in metricParams.evals and
        metricParams.evecs (ie. we must know how to do the transformation for
        the given value of fUpper)

    Returns
    --------
    mus : list of floats or numpy.arrays
        Position of the system(s) in the mu coordinate system
    """

    # Do this by masses -> lambdas
    lambdas = get_chirp_params(totmass, eta, beta, sigma, gamma, chis, \
                               metricParams.f0, metricParams.pnOrder)
    # and lambdas -> mus
    mus = get_mu_params(lambdas, metricParams, fUpper)
    return mus

def get_mu_params(lambdas, metricParams, fUpper):
    """
    Function to rotate from the lambda coefficients into position in the mu
    coordinate system. Mu = Cartesian metric, but not principal components.

    Parameters
    -----------
    lambdas : list of floats or numpy.arrays
        Position of the system(s) in the lambda coefficients
    metricParams : metricParameters instance
        Structure holding all the options for construction of the metric
        and the eigenvalues, eigenvectors and covariance matrix
        needed to manipulate the space.
    fUpper : float
        The value of fUpper to use when getting the mu coordinates from the
        lambda coordinates. This must be a key in metricParams.evals and
        metricParams.evecs (ie. we must know how to do the transformation for
        the given value of fUpper)

    Returns
    --------
    mus : list of floats or numpy.arrays
        Position of the system(s) in the mu coordinate system
    """
    evecs = metricParams.evecs[fUpper]
    evals = metricParams.evals[fUpper]

    mus = []
    for i in range(len(evals)):
        mus.append(rotate_vector(evecs,lambdas,numpy.sqrt(evals[i]),i))
    return mus

def get_covaried_params(mus, evecsCV):
    """
    Function to rotate from position(s) in the mu_i coordinate system into the
    position(s) in the xi_i coordinate system

    Parameters
    -----------
    mus : list of floats or numpy.arrays
        Position of the system(s) in the mu coordinate system
    evecsCV : numpy.matrix
        This matrix is used to perform the rotation to the xi_i
        coordinate system.

    Returns
    --------
    xis : list of floats or numpy.arrays
        Position of the system(s) in the xi coordinate system
    """
    xis = []
    for i in range(len(evecsCV)):
        xis.append(rotate_vector(evecsCV,mus,1.,i))
    return xis

def rotate_vector(evecs, old_vector, rescale_factor, index):
    """
    Function to find the position of the system(s) in one of the xi_i or mu_i
    directions.

    Parameters
    -----------
    evecs : numpy.matrix
        Matrix of the eigenvectors of the metric in lambda_i coordinates. Used
        to rotate to a Cartesian coordinate system.
    old_vector : list of floats or numpy.arrays
        The position of the system(s) in the original coordinates
    rescale_factor : float
        Scaling factor to apply to resulting position(s)
    index : int
        The index of the final coordinate system that is being computed. Ie.
        if we are going from mu_i -> xi_j, this will give j.

    Returns
    --------
    positions : float or numpy.array
        Position of the point(s) in the resulting coordinate.
    """
    temp = 0
    for i in range(len(evecs)):
        temp += evecs[i,index] * old_vector[i]
    temp *= rescale_factor
    return temp

def get_point_distance(point1, point2, metricParams, fUpper):
    """
    Function to calculate the mismatch between two points, supplied in terms
    of the masses and spins, using the xi_i parameter space metric to
    approximate the mismatch of the two points. Can also take one of the points
    as an array of points and return an array of mismatches (but only one can
    be an array!)

    point1 : List of floats or numpy.arrays
        point1[0] contains the mass(es) of the heaviest body(ies).
        point1[1] contains the mass(es) of the smallest body(ies).
        point1[2] contains the spin(es) of the heaviest body(ies).
        point1[3] contains the spin(es) of the smallest body(ies).
    point2 : List of floats
        point2[0] contains the mass of the heaviest body.
        point2[1] contains the mass of the smallest body.
        point2[2] contains the spin of the heaviest body.
        point2[3] contains the spin of the smallest body.
    metricParams : metricParameters instance
        Structure holding all the options for construction of the metric
        and the eigenvalues, eigenvectors and covariance matrix
        needed to manipulate the space.
    fUpper : float
        The value of fUpper to use when getting the mu coordinates from the
        lambda coordinates. This must be a key in metricParams.evals,
        metricParams.evecs and metricParams.evecsCV
        (ie. we must know how to do the transformation for
        the given value of fUpper)

    Returns
    --------
    dist : float or numpy.array
        Distance between the point2 and all points in point1
    xis1 : List of floats or numpy.arrays
        Position of the input point1(s) in the xi_i parameter space
    xis2 : List of floats
        Position of the input point2 in the xi_i parameter space
    """
    aMass1 = point1[0]
    aMass2 = point1[1]
    aSpin1 = point1[2]
    aSpin2 = point1[3]
    try:
        leng = len(aMass1)
        aArray = True
    except:
        aArray = False

    bMass1 = point2[0]
    bMass2 = point2[1]
    bSpin1 = point2[2]
    bSpin2 = point2[3]
    bArray = False

    aTotMass = aMass1 + aMass2
    aEta = (aMass1 * aMass2) / (aTotMass * aTotMass)
    aCM = aTotMass * aEta**(3./5.)

    bTotMass = bMass1 + bMass2
    bEta = (bMass1 * bMass2) / (bTotMass * bTotMass)
    bCM = bTotMass * bEta**(3./5.)

    abeta, asigma, agamma, achis = pnutils.get_beta_sigma_from_aligned_spins(
        aEta, aSpin1, aSpin2)
    bbeta, bsigma, bgamma, bchis = pnutils.get_beta_sigma_from_aligned_spins(
        bEta, bSpin1, bSpin2)

    aXis = get_cov_params(aTotMass, aEta, abeta, asigma, agamma, achis, \
                          metricParams, fUpper)

    bXis = get_cov_params(bTotMass, bEta, bbeta, bsigma, bgamma, bchis, \
                          metricParams, fUpper)

    dist = (aXis[0] - bXis[0])**2
    for i in range(1,len(aXis)):
        dist += (aXis[i] - bXis[i])**2

    return dist, aXis, bXis

def calc_point_dist(vsA, entryA, MMdistA):
    """
    This function is used to determine if the distance between two points is
    less than that stated by the minimal match.

    Parameters
    ----------
    vsA : list or numpy.array or similar
        An array of point 1's position in the \chi_i coordinate system
    entryA : list or numpy.array or similar
        An array of point 2's position in the \chi_i coordinate system
    MMdistA : float
        The minimal mismatch allowed between the points

    Returns
    --------
    Boolean
        True if the points have a mismatch < MMdistA
        False if the points have a mismatch > MMdistA
    """
    val = (vsA[0] - entryA[0])**2
    for i in range(1,len(vsA)):
        val += (vsA[i] - entryA[i])**2
    return (val < MMdistA)

def calc_point_dist_vary(mus1, fUpper1, mus2, fUpper2, fMap, norm_map, MMdistA):
    """
    Function to determine if two points, with differing upper frequency cutoffs
    have a mismatch < MMdistA for *both* upper frequency cutoffs.

    Parameters
    ----------
    mus1 : List of numpy arrays
        mus1[i] will give the array of point 1's position in the \chi_j
        coordinate system. The i element corresponds to varying values of the
        upper frequency cutoff. fMap is used to map between i and actual
        frequencies
    fUpper1 : float
        The upper frequency cutoff of point 1.
    mus2 : List of numpy arrays
        mus2[i] will give the array of point 2's position in the \chi_j
        coordinate system. The i element corresponds to varying values of the
        upper frequency cutoff. fMap is used to map between i and actual
        frequencies
    fUpper2 : float
        The upper frequency cutoff of point 2.
    fMap : dictionary
        fMap[fUpper] will give the index needed to get the \chi_j coordinates
        in the two sets of mus
    norm_map : dictionary
        norm_map[fUpper] will give the relative frequency domain template
        amplitude (sigma) at the given value of fUpper.
    MMdistA
        The minimal mismatch allowed between the points

    Returns
    --------
    Boolean
        True if the points have a mismatch < MMdistA
        False if the points have a mismatch > MMdistA
    """
    f_upper = min(fUpper1, fUpper2)
    f_other = max(fUpper1, fUpper2)
    idx = fMap[f_upper]
    vecs1 = mus1[idx]
    vecs2 = mus2[idx]
    val = ((vecs1 - vecs2)*(vecs1 - vecs2)).sum()
    if (val > MMdistA):
        return False
    # Reduce match to account for normalization.
    norm_fac = norm_map[f_upper] / norm_map[f_other]
    val = 1 - (1 - val)*norm_fac
    return (val < MMdistA)

def return_nearest_cutoff(name, totmass, freqs):
    """
    Given an array of total mass values and an (ascending) list of
    frequencies, this will calculate the specified cutoff formula for each
    mtotal and return the nearest frequency to each cutoff from the input
    list.
    Currently only supports cutoffs that are functions of the total mass
    and no other parameters (SchwarzISCO, LightRing, ERD)

    Parameters
    ----------
    name : string
        Name of the cutoff formula to be approximated
    totmass : numpy.array
        The total mass of the input systems
    freqs : list of floats
        A list of frequencies (must be sorted ascending)

    Returns
    -------
    numpy.array
        The frequencies closest to the cutoff for each value of totmass.
    """
    cutoffFns = {
        "SchwarzISCO": pnutils.f_SchwarzISCO,
        "LightRing"  : pnutils.f_LightRing,
        "ERD"        : pnutils.f_ERD
    }
    f_cutoff = cutoffFns[name](totmass)
    # FIXME: Ian's not entirely sure how this works!  Documentation may be
    # wrong.
    refEv = numpy.zeros(len(f_cutoff),dtype=float)
    for i in range(len(freqs)):
        if (i == 0):
            logicArr = f_cutoff < ((freqs[0] + freqs[1])/2.)
        elif (i == (len(freqs)-1)):
            logicArr = f_cutoff > ((freqs[-2] + freqs[-1])/2.)
        else:
            logicArrA = f_cutoff > ((freqs[i-1] + freqs[i])/2.)
            logicArrB = f_cutoff < ((freqs[i] + freqs[i+1])/2.)
            logicArr = numpy.logical_and(logicArrA,logicArrB)
        if logicArr.any():
            refEv[logicArr] = freqs[i]
    return refEv

def outspiral_loop(N):
    """
    Return a list of points that will loop outwards in a 2D lattice in terms
    of distance from a central point. So if N=2 this will be [0,0], [0,1],
    [0,-1],[1,0],[-1,0],[1,1] .... This is useful when you want to loop over
    a number of bins, but want to start in the center and work outwards.
    """
    # Create a 2D lattice of all points
    X,Y = numpy.meshgrid(numpy.arange(-N,N+1), numpy.arange(-N,N+1))

    # Flatten it
    X = numpy.ndarray.flatten(X)
    Y = numpy.ndarray.flatten(Y)

    # Force to an integer
    X = numpy.array(X, dtype=int)
    Y = numpy.array(Y, dtype=int)
   
    # Calculate distances
    G = numpy.sqrt(X**2+Y**2)

    # Combine back into an array
    out_arr = numpy.array([X,Y,G])
   
    # And order correctly
    sorted_out_arr = out_arr[:,out_arr[2].argsort()]

    return sorted_out_arr[:2,:].T

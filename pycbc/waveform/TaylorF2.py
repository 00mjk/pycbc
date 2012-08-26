import lalsimulation
import lal
import numpy
import pycuda.tools
from pycuda.elementwise import ElementwiseKernel
from pycbc.types import FrequencySeries,zeros
from pycuda.gpuarray import to_gpu
from numpy import sqrt

pntype = numpy.dtype([('pfaN', numpy.float64),
                    ('pfa2', numpy.float64),
                    ('pfa3', numpy.float64),
                    ('pfa4', numpy.float64),
                    ('pfa5', numpy.float64),
                    ('pfl5', numpy.float64),
                    ('pfa6', numpy.float64),
                    ('pfl6', numpy.float64),
                    ('pfa7', numpy.float64),
                    ('delta_f',numpy.float64),
                    ('FTaN',numpy.float64),
                    ('piM',numpy.float64),
                    ('amp0',numpy.float64),
                    ('dEtaN',numpy.float64),
                    ('kmin',numpy.float64),
                    ('phi0',numpy.float64),
                    ('tC',numpy.float64),
                    ('phase0', numpy.int64),
                     ])
pycuda.tools.register_dtype(pntype,"pntype")

def get_taylorf2_pn_coefficients(mass1,mass2,distance,beta =0 , sigma = 0):
    
    M = float(mass1) + float(mass2)
    eta = mass1 * mass2 / (M * M)
    theta = -11831./9240.;
    lambdaa = -1987./3080.0;
    pfaN = 3.0/(128.0 * eta);
    pfa2 = 5*(743.0/84 + 11.0 * eta)/9.0;
    pfa3 = -16.0*lal.LAL_PI + 4.0*beta;
    pfa4 = 5.0*(3058.673/7.056 + 5429.0/7.0 * eta + 617.0 * eta*eta)/72.0 - 10.0*sigma
    pfa5 = 5.0/9.0 * (7729.0/84.0 - 13.0 * eta) * lal.LAL_PI
    pfl5 = 5.0/3.0 * (7729.0/84.0 - 13.0 * eta) * lal.LAL_PI
    pfa6 = (11583.231236531/4.694215680 - 640.0/3.0 * lal.LAL_PI * lal.LAL_PI - 6848.0/21.0*lal.LAL_GAMMA) + eta * (-15335.597827/3.048192 + 2255./12. * lal.LAL_PI * lal.LAL_PI - 1760./3.*theta +12320./9.*lambdaa) + eta*eta * 76055.0/1728.0 - eta*eta*eta*  127825.0/1296.0 
    pfl6 = -6848.0/21.0;
    pfa7 = lal.LAL_PI * 5.0/756.0 * ( 15419335.0/336.0 + 75703.0/2.0 * eta - 14809.0 * eta*eta)

    FTaN = 32.0 * eta*eta / 5.0;

    dETaN = -eta;
  
    amp0 = 4. * mass1 * mass2 / float(distance) * lal.LAL_MRSUN_SI * lal.LAL_MTSUN_SI * sqrt(lal.LAL_PI/12.0)    
    
    m_sec = M * lal.LAL_MTSUN_SI;
    piM = lal.LAL_PI * m_sec; 

    pn_coefficients = numpy.array((pfaN,pfa2,pfa3,pfa4,pfa5,pfl5,pfa6,pfl6,pfa7,0,FTaN,piM,amp0,dETaN,0,0,0,0),dtype=pntype)

    return pn_coefficients

preamble = """
#include <lal/LALConstants.h>

struct pntype{
double pfaN;
double pfa2;
double pfa3;
double pfa4;
double pfa5;
double pfl5;
double pfa6;
double pfl6;
double pfa7;
double delta_f;
double FTaN;
double piM;
double amp0;
double dETaN;
double kmin;
double phi0;
double tC;
long phaseO;
};
"""
 
taylorf2_text = """

    const double f = (i +cf->kmin) * cf->delta_f;
    const double v0 = cbrt(cf->piM * 14.0);
    const double v = cbrt(cf->piM*f);
    const double v2 = v * v;
    const double v3 = v * v2;
    const double v4 = v * v3;
    const double v5 = v * v4;
    const double v6 = v * v5;
    const double v7 = v * v6;
    const double v8 = v * v7;
    const double v9 = v * v8;
    const double v10 = v * v9;
    double phasing = 0.;
    double dEnergy = 0.;
    double flux = 0.;
    double amp;
    double shft = -LAL_TWOPI * cf->tC;
    double phi0 = cf->phi0;

    switch (cf->phaseO)
    {
        case -1:
        case 7:
            phasing += cf->pfa7 * v7;
        case 6:
            phasing += (cf->pfa6 + cf->pfl6 * log(4.*v) ) * v6;
        case 5:
            phasing += (cf->pfa5 + cf->pfl5 * log(v/v0)) * v5;
        case 4:
            phasing += cf->pfa4 * v4;
        case 3:
            phasing += cf->pfa3 * v3;
        case 2:
            phasing += cf->pfa2 * v2;
        case 0:
            phasing += 1.;
            break;
        default:
            break;
    }

    flux+=1.0;
    dEnergy+=1.0;

    phasing *= cf->pfaN / v5;
    flux *= cf->FTaN * v10;
    dEnergy *= cf->dETaN * v;

    phasing += shft * f + phi0;
    amp = cf->amp0 * sqrt(-dEnergy/flux) * v;
    htilde[i]._M_re = amp * cos(phasing + LAL_PI_4) ;
    htilde[i]._M_im = - amp * sin(phasing + LAL_PI_4);

"""

taylorf2_kernel = ElementwiseKernel("pycuda::complex<double> *htilde, pntype *cf",
                    taylorf2_text, "taylorf2_kernel",preamble=preamble)

def taylorf2(length,delta_f,mass1,mass2,fstart,phiC=0,tC=0,distance=1,phase_order=7,beta =0 , sigma = 0 ):
    pn_const = get_taylorf2_pn_coefficients(mass1,mass2,distance,beta,sigma)
    pn_const['phase0'] = int(phase_order)
    pn_const['delta_f'] = delta_f
    pn_const['phi0']=phiC
    pn_const['tC']=tC

    kmin = int(fstart / float(delta_f))

    piM = pn_const['piM']
    vISCO = 1. / sqrt(6.);
    fISCO = vISCO * vISCO * vISCO / piM;
    kmax = int(fISCO / delta_f)
    pn_const['kmin'] = kmin
    print vISCO, piM,fISCO
    print kmin ,kmax
    htilde = FrequencySeries(zeros(length,dtype=numpy.complex128),delta_f = delta_f, copy=False)
    taylorf2_kernel(htilde.data[kmin:kmax],to_gpu(pn_const))
    return htilde
    



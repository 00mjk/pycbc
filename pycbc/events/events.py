# Copyright (C) 2012  Alex Nitz
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# self.option) any later version.
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
"""This modules defines functions for clustering and thresholding timeseries to
produces event triggers
"""
import glue.ligolw.utils.process
import lal
import numpy
import copy
import pycbc
from pycbc.types import Array
from pycbc.scheme import schemed
import numpy

@schemed("pycbc.events.threshold_")
def threshold(series, value):
    """Return list of values and indices values over threshold in series.
    """

@schemed("pycbc.events.threshold_")
def threshold_and_cluster(series, threshold, window):
    """Return list of values and indices values over threshold in series.
    """

def fc_cluster_over_window_fast(times, values, window_length):
    """ Reduce the events by clustering over a window using
    the FindChirp clustering algorithm

    Parameters
    -----------
    indices: Array
        The list of indices of the SNR values
    snr: Array
        The list of SNR value
    window_size: int
        The size of the window in integer samples.

    Returns
    -------
    indices: Array
        The reduced list of indices of the SNR values
    """
    if window_length <= 0:
        return times

    from scipy.weave import inline
    indices = numpy.zeros(len(times), dtype=int)
    tlen = len(times)
    k = numpy.zeros(1, dtype=int)
    absvalues = abs(values)
    times = times.astype(int)
    code = """
        int j = 0;
        for (int i=0; i < tlen; i++){
            if ((times[i] - times[indices[j]]) > window_length){
                j += 1;
                indices[j] = i;
            }
            else if (absvalues[i] > absvalues[indices[j]]){
                indices[j] = i;
            }
        }
        k[0] = j;
    """
    inline(code, ['times', 'absvalues', 'window_length', 'indices', 'tlen', 'k'],
                 extra_compile_args=['-march=native -O3 -w'])
    return indices[0:k[0]+1]

def cluster_reduce(idx, snr, window_size):
    """ Reduce the events by clustering over a window

    Parameters
    -----------
    indices: Array
        The list of indices of the SNR values
    snr: Array
        The list of SNR value
    window_size: int
        The size of the window in integer samples.

    Returns
    -------
    indices: Array
        The list of indices of the SNR values
    snr: Array
        The list of SNR values
    """
    ind = fc_cluster_over_window_fast(idx, snr, window_size)
    return idx.take(ind), snr.take(ind)

def findchirp_cluster_over_window(times, values, window_length):
    indices = numpy.zeros(len(times), dtype=int)
    j = 0
    for i in xrange(len(times)):
        if times[i] - times[indices[j]] > window_length:
            j += 1
            indices[j] = i
        else:
            if abs(values[i]) > abs(values[indices[j]]):
                indices[j] = i
            else:
                continue
    return indices[0:j+1]

def newsnr(snr, reduced_x2, q=6.):
    """Calculate the re-weighted SNR statistic ('newSNR') from given SNR and
    reduced chi-squared values. See http://arxiv.org/abs/1208.3491 for
    definition.
    """
    newsnr = numpy.array(snr, ndmin=1)
    reduced_x2 = numpy.array(reduced_x2, ndmin=1)

    # newsnr is only different from snr if reduced chisq > 1
    ind = numpy.where(reduced_x2 > 1.)[0]
    newsnr[ind] *= ( 0.5 * (1. + reduced_x2[ind] ** (q/2.)) ) ** (-1./q)

    if len(newsnr) > 1:
        return newsnr
    else:
        return newsnr[0]

class EventManager(object):
    def __init__(self, opt, column, column_types, **kwds):
        self.opt = opt
        self.global_params = kwds

        self.event_dtype = [ ('template_id', int) ]
        for column, coltype in zip (column, column_types):
            self.event_dtype.append( (column, coltype) )

        self.events = numpy.events = numpy.array([], dtype=self.event_dtype)
        self.template_params = []
        self.template_index = -1
        self.template_events = numpy.array([], dtype=self.event_dtype)

    def chisq_threshold(self, value, num_bins, delta=0):
        remove = []
        for i, event in enumerate(self.events):
            xi = event['chisq'] / (event['chisq_dof'] + delta * event['snr'].conj() * event['snr'])
            if xi > value:
                remove.append(i)
        self.events = numpy.delete(self.events, remove)

    def newsnr_threshold(self, threshold):
        """ Remove events with newsnr smaller than given threshold
        """
        if not self.opt.chisq_bins:
            raise RuntimeError('Chi-square test must be enabled in order to use newsnr threshold')

        remove = [i for i, e in enumerate(self.events) if \
            newsnr(abs(e['snr']), e['chisq'] / (2 * e['chisq_dof'] - 2)) < threshold]
        self.events = numpy.delete(self.events, remove)

    def maximize_over_bank(self, tcolumn, column, window):
        if len(self.events) == 0:
            return

        self.events = numpy.sort(self.events, order=tcolumn)
        cvec = self.events[column]
        tvec = self.events[tcolumn]

        indices = []
#        mint = tvec.min()
#        maxt = tvec.max()
#        edges = numpy.arange(mint, maxt, window)

#        # Get the location of each time bin
#        bins = numpy.searchsorted(tvec, edges)
#        bins = numpy.append(bins, len(tvec))
#        for i in range(len(bins)-1):
#            kmin = bins[i]
#            kmax = bins[i+1]
#            if kmin == kmax:
#                continue
#            event_idx = numpy.argmax(cvec[kmin:kmax]) + kmin
#            indices.append(event_idx)

        # This algorithm is confusing, but it is what lalapps_inspiral does
        # REMOVE ME!!!!!!!!!!!
        gps = tvec.astype(numpy.float64) / self.opt.sample_rate + self.opt.gps_start_time
        gps_sec  = numpy.floor(gps)
        gps_nsec = (gps - gps_sec) * 1e9

        wnsec = int(window * 1e9 / self.opt.sample_rate)
        win = gps_nsec.astype(int) / wnsec

        indices.append(0)
        for i in xrange(len(tvec)):
            if gps_sec[i] == gps_sec[indices[-1]] and  win[i] == win[indices[-1]]:
                    if abs(cvec[i]) > abs(cvec[indices[-1]]):
                        indices[-1] = i
            else:
                indices.append(i)

        self.events = numpy.take(self.events, indices)

    def add_template_events(self, columns, vectors):
        """ Add a vector indexed """
        # initialize with zeros - since vectors can be None, look for the
        # first one that isn't
        new_events = None
        for v in vectors:
            if v is not None:
                new_events = numpy.zeros(len(v), dtype=self.event_dtype)
                break
        # they shouldn't all be None
        assert new_events is not None
        new_events['template_id'] = self.template_index
        for c, v in zip(columns, vectors):
            if v is not None:
                if isinstance(v, Array):
                    new_events[c] = v.numpy()
                else:
                    new_events[c] = v
        self.template_events = numpy.append(self.template_events, new_events)

    def cluster_template_events(self, tcolumn, column, window_size):
        """ Cluster the internal events over the named column
        """
        cvec = self.template_events[column]
        tvec = self.template_events[tcolumn]
        #indices = findchirp_cluster_over_window(tvec, cvec, window_size)
        indices = fc_cluster_over_window_fast(tvec, cvec, window_size)
        self.template_events = numpy.take(self.template_events, indices)

    def new_template(self, **kwds):
        self.template_params.append(kwds)
        self.template_index += 1

    def add_template_params(self, **kwds):
        self.template_params[-1].update(kwds)

    def finalize_template_events(self):
        self.events = numpy.append(self.events, self.template_events)
        self.template_events = numpy.array([], dtype=self.event_dtype)

    def write_events(self, outname):
        """ Write the found events to a sngl inspiral table
        """

        if '.xml' in outname:
            self.write_to_xml(outname)
        elif '.hdf' in outname:
            self.write_to_hdf(outname)
        else:
            raise ValueError('Cannot write to this format')
    
    def write_to_hdf(self, outname):
        import h5py
        f = h5py.File(outname, 'w')
        
        if len(self.events):
            f.create_dataset('snr', data=abs(self.events['snr']), compression='gzip')
            f.create_dataset('coa_phase', data=numpy.angle(self.events['snr']), compression='gzip')
            f.create_dataset('chisq', data=abs(self.events['chisq']), compression='gzip')
            f.create_dataset('bank_chisq', data=abs(self.events['bank_chisq']), compression='gzip')
            f.create_dataset('cont_chisq', data=abs(self.events['cont_chisq']), compression='gzip')
            
            end_time = self.events['time_index'] / float(self.opt.sample_rate) + self.opt.gps_start_time
            f.create_dataset('end_time', data=end_time, compression='gzip')
            
            tid = self.events['template_id']
            template_sigmasq = numpy.array([t['sigmasq'] for t in self.template_params], dtype=numpy.float32)
            f.create_dataset('sigmasq', data=template_sigmasq[tid], compression='gzip')
         
            cont_dof = self.opt.autochi_number_points if self.opt.autochi_onesided else 2 * self.opt.autochi_number_points
            f.create_dataset('cont_chisq_dof', data=numpy.repeat(cont_dof, len(self.events)), compression='gzip')
            f.create_dataset('bank_chisq_dof', data=numpy.repeat(10, len(self.events)), compression='gzip')        

            if 'chisq_dof' in self.events.dtype.names:
                f.create_dataset('chisq_dof', data=self.events['chisq_dof'] / 2 + 1, compression='gzip')
            else:
                f.create_dataset('chisq_dof', data=numpy.zeros(len(self.events)), compression='gzip')    
        
            # Template id hack
            m1 = numpy.array([p['tmplt'].mass1 for p in self.template_params], dtype=numpy.float32)
            m2 = numpy.array([p['tmplt'].mass2 for p in self.template_params], dtype=numpy.float32)
            s1 = numpy.array([p['tmplt'].spin1z for p in self.template_params], dtype=numpy.float32)
            s2 = numpy.array([p['tmplt'].spin2z for p in self.template_params], dtype=numpy.float32)
        
            th = numpy.zeros(len(m1), dtype=int)
            for j, v in enumerate(zip(m1, m2, s1, s2)):
                th[j] = hash(v)
            th_sort = th.argsort()
        
            th_map  = {}
            for j, h in enumerate(th[th_sort]):
                th_map[h] = j
            
            rtid = numpy.array([th_map[h] for h in th])
            f.create_dataset('template_id', data=rtid[tid], compression='gzip') 
    
        f.attrs['ifo'] = self.opt.channel_name[0:2]
        if self.opt.trig_start_time:
            f['search/start_time'] = numpy.array([self.opt.trig_start_time])
        else:
            f['search/start_time'] = numpy.array([self.opt.gps_start_time + self.opt.segment_start_pad])
            
        if self.opt.trig_end_time:
            f['search/end_time'] = numpy.array([self.opt.trig_end_time])
        else:
            f['search/end_time'] = numpy.array([self.opt.gps_end_time - self.opt.segment_end_pad])

    def write_to_xml(self, outname):
        """ Write the found events to a sngl inspiral table 
        """
        outdoc = glue.ligolw.ligolw.Document()
        outdoc.appendChild(glue.ligolw.ligolw.LIGO_LW())

        ifo = self.opt.channel_name[0:2]

        proc_id = glue.ligolw.utils.process.register_to_xmldoc(outdoc,
                        "inspiral", self.opt.__dict__, comment="", ifos=[ifo],
                        version=glue.git_version.id, cvs_repository=glue.git_version.branch,
                        cvs_entry_time=glue.git_version.date).process_id

        # Create sngl_inspiral table ###########################################
        sngl_table = glue.ligolw.lsctables.New(glue.ligolw.lsctables.SnglInspiralTable)
        outdoc.childNodes[0].appendChild(sngl_table)

        start_time = lal.LIGOTimeGPS(self.opt.gps_start_time)

        if self.opt.trig_start_time:
            tstart_time = self.opt.trig_start_time
        else:
            tstart_time = self.opt.gps_start_time + self.opt.segment_start_pad

        if self.opt.trig_end_time:
            tend_time = self.opt.trig_end_time
        else:
            tend_time = self.opt.gps_end_time - self.opt.segment_end_pad

        for event_num, event in enumerate(self.events):
            tind = event['template_id']

            tmplt = self.template_params[tind]['tmplt']
            sigmasq = self.template_params[tind]['sigmasq']

            row = copy.deepcopy(tmplt)

            snr = event['snr']
            idx = event['time_index']
            end_time = start_time + float(idx) / self.opt.sample_rate

            row.channel = self.opt.channel_name[3:]
            row.ifo = ifo

            # FIXME: This is *not* the dof!!!
            # but is needed for later programs not to fail
            if 'chisq_dof' in event.dtype.names:
                # fail through: copy the value from the trigger
                row.chisq_dof = event['chisq_dof'] / 2 + 1
            else:
                row.chisq_dof = 0

            if hasattr(self.opt, 'bank_veto_bank_file') and self.opt.bank_veto_bank_file:
                # EXPLAINME - is this a hard-coding? Certainly looks like one
                row.bank_chisq_dof = 10
                row.bank_chisq = event['bank_chisq']
            else:
                row.bank_chisq_dof = 0
                row.bank_chisq = 0

            if hasattr(self.opt, 'autochi_number_points') and self.opt.autochi_number_points>0:
                row.cont_chisq = event['cont_chisq']
                if (self.opt.autochi_onesided):
                    row.cont_chisq_dof = self.opt.autochi_number_points
                else:    
                    row.cont_chisq_dof = 2*self.opt.autochi_number_points

            row.eff_distance = sigmasq ** (0.5) / abs(snr)
            row.snr = abs(snr)
            row.end_time = int(end_time.gpsSeconds)
            row.end_time_ns = int(end_time.gpsNanoSeconds)
            row.process_id = proc_id
            row.coa_phase = numpy.angle(snr)
            row.sigmasq = sigmasq

            row.event_id = glue.ligolw.lsctables.SnglInspiralID(event_num)

            sngl_table.append(row)

        # Create Search Summary Table ########################################
        search_summary_table = glue.ligolw.lsctables.New(glue.ligolw.lsctables.SearchSummaryTable)
        outdoc.childNodes[0].appendChild(search_summary_table)

        row = glue.ligolw.lsctables.SearchSummary()
        row.nevents = len(sngl_table)
        row.process_id = proc_id
        row.shared_object = ""
        row.lalwrapper_cvs_tag = ""
        row.lal_cvs_tag = ""
        row.comment = ""
        row.ifos = ifo
        row.in_start_time = self.opt.gps_start_time - self.opt.pad_data
        row.in_start_time_ns = 0
        row.in_end_time = self.opt.gps_end_time + self.opt.pad_data
        row.in_end_time_ns = 0
        row.out_start_time = tstart_time
        row.out_start_time_ns = 0
        row.out_end_time = tend_time
        row.out_end_time_ns = 0
        row.nnodes = 1

        search_summary_table.append(row)

        # Create Filter Table ########################################
        filter_table = glue.ligolw.lsctables.New(glue.ligolw.lsctables.FilterTable)
        outdoc.childNodes[0].appendChild(filter_table)

        row = glue.ligolw.lsctables.Filter()
        row.process_id = proc_id
        row.program = "PyCBC_INSPIRAL"
        row.start_time = self.opt.gps_start_time
        row.filter_name = self.opt.approximant
        row.param_set = 0
        row.comment = ""
        row.filter_id = str(glue.ligolw.lsctables.FilterID(0))

        filter_table.append(row)

        # SumVars Table ########################################
        search_summvars_table = glue.ligolw.lsctables.New(glue.ligolw.lsctables.SearchSummVarsTable)
        outdoc.childNodes[0].appendChild(search_summvars_table)

        row = glue.ligolw.lsctables.SearchSummVars()
        row.process_id = proc_id
        row.name = "raw data sample rate"
        row.string = ""
        row.value = 1.0 /16384
        row.search_summvar_id = str(glue.ligolw.lsctables.SearchSummVarsID(0))
        search_summvars_table.append(row)

        row = glue.ligolw.lsctables.SearchSummVars()
        row.process_id = proc_id
        row.name = "filter data sample rate"
        row.string = ""
        row.value = 1.0 / self.opt.sample_rate
        row.search_summvar_id = str(glue.ligolw.lsctables.SearchSummVarsID(1))
        search_summvars_table.append(row)

        # SumValue Table ########################################
        summ_val_columns = ['program', 'process_id', 'start_time',
                            'start_time_ns', 'end_time', 'end_time_ns', 'ifo',
                            'name', 'value', 'comment', 'summ_value_id']
        summ_value_table = glue.ligolw.lsctables.New(
                glue.ligolw.lsctables.SummValueTable, columns=summ_val_columns)
        outdoc.childNodes[0].appendChild(summ_value_table)

        row = glue.ligolw.lsctables.SummValue()
        row.process_id = proc_id
        row.start_time = tstart_time
        row.start_time_ns = 0
        row.end_time = tend_time
        row.end_time_ns = 0
        row.ifo = ifo
        row.frameset_group = ""
        row.program = "PyCBC-INSPIRAL"
        row.error = 0
        row.intvalue = 0

        row1 = copy.deepcopy(row)
        row2 = copy.deepcopy(row)
        row3 = copy.deepcopy(row)
        row1.name = "inspiral_effective_distance"

        psd = self.global_params['psd']
        from pycbc.waveform.spa_tmplt import spa_distance
        from pycbc import DYN_RANGE_FAC
        row1.value = spa_distance(psd, 1.4, 1.4, self.opt.low_frequency_cutoff,
                                                         snr=8) * DYN_RANGE_FAC
        row1.comment = "1.4_1.4_8"
        row1.summ_value_id = str(glue.ligolw.lsctables.SummValueID(0))
        summ_value_table.append(row1)

        row2.name = "calibration alpha"
        row2.value = 0
        row2.comment = "analysis"
        row2.summ_value_id = str(glue.ligolw.lsctables.SummValueID(1))
        summ_value_table.append(row2)

        row3.name = "calibration alphabeta"
        row3.value = 0
        row3.comment = "analysis"
        row3.summ_value_id = str(glue.ligolw.lsctables.SummValueID(2))
        summ_value_table.append(row3)

        # Write out file #####################################################
        glue.ligolw.utils.write_filename(outdoc, outname, gz=outname.endswith('gz'))


__all__ = ['threshold_and_cluster', 'newsnr',
           'findchirp_cluster_over_window', 'fc_cluster_over_window_fast',
           'threshold', 'cluster_reduce',
           'EventManager']


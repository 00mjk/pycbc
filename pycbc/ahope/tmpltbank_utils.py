# Copyright (C) 2013  Ian Harry
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
This module is responsible for setting up the template bank stage of ahope
workflows. For details about this module and its capabilities see here:
https://ldas-jobs.ligo.caltech.edu/~cbc/docs/pycbc/ahope/template_bank.html
"""

from __future__ import division

import os
import urlparse, urllib
import logging
from glue import segments
from pycbc.ahope.ahope_utils import *
from pycbc.ahope.jobsetup_utils import *

def setup_tmpltbank_workflow(workflow, science_segs, datafind_outs,
                             output_dir=None, tags=[]):
    '''
    Setup template bank section of ahope workflow. This function is responsible
    for deciding which of the various template bank workflow generation
    utilities should be used.

    Parameters
    ----------
    workflow: Workflow
        An instanced class that manages the constructed workflow.
    science_segs : Keyed dictionary of glue.segmentlist objects
        scienceSegs[ifo] holds the science segments to be analysed for each
        ifo. 
    datafind_outs : AhopeFileList
        The file list containing the datafind files.
    output_dir : path string
        The directory where data products will be placed. 
    tags : list of strings
        If given these tags are used to uniquely name and identify output files
        that would be produced in multiple calls to this function.

    Returns
    --------
    AhopeFileList
        The AhopeFileList holding the details of all the template bank jobs.
    '''
    logging.info("Entering template bank generation module.")
    make_analysis_dir(output_dir)
    cp = workflow.cp
    
    # Parse for options in ini file
    tmpltbankMethod = cp.get_opt_tags("ahope-tmpltbank", "tmpltbank-method",
                                      tags)

    # There can be a large number of different options here, for e.g. to set
    # up fixed bank, or maybe something else
    if tmpltbankMethod == "PREGENERATED_BANK":
        logging.info("Setting template bank from pre-generated bank(s).")
        tmplt_banks = setup_tmpltbank_pregenerated(workflow, tags=tags)
    # Else we assume template banks will be generated in the workflow
    elif tmpltbankMethod == "WORKFLOW_INDEPENDENT_IFOS":
        logging.info("Adding template bank jobs to workflow.")
        if cp.has_option_tags("ahope-tmpltbank",
                              "tmpltbank-link-to-matchedfilter", tags):
            if not cp.has_option_tags("ahope-matchedfilter",
                              "matchedfilter-link-to-tmpltbank", tags):
                errMsg = "If using tmpltbank-link-to-matchedfilter, you should "
                errMsg = "also use matchedfilter-link-to-tmpltbank."
                logging.warn(errMsg)
            linkToMatchedfltr = True
        tmplt_banks = setup_tmpltbank_dax_generated(workflow, science_segs,
                                         datafind_outs, output_dir, tags=tags,
                                         link_to_matchedfltr=linkToMatchedfltr)
    elif tmpltbankMethod == "WORKFLOW_INDEPENDENT_IFOS_NODATA":
        logging.info("Adding template bank jobs to workflow.")
        tmplt_banks = setup_tmpltbank_without_frames(workflow, output_dir,
                                         tags=tags, independent_ifos=True)
    elif tmpltbankMethod == "WORKFLOW_NO_IFO_VARIATION_NODATA":
        logging.info("Adding template bank jobs to workflow.")
        tmplt_banks = setup_tmpltbank_without_frames(workflow, output_dir,
                                         tags=tags, independent_ifos=False)
    else:
        errMsg = "Template bank method not recognized. Must be either "
        errMsg += "PREGENERATED_BANK, WORKFLOW_INDEPENDENT_IFOS "
        errMsg += "or WORKFLOW_INDEPENDENT_IFOS_NODATA."
        raise ValueError(errMsg)
    
    logging.info("Leaving template bank generation module.")
    return tmplt_banks

def setup_tmpltbank_dax_generated(workflow, science_segs, datafind_outs,
                                  output_dir, tags=[],
                                  link_to_matchedfltr=True):
    '''
    Setup template bank jobs that are generated as part of the ahope workflow.
    This function will add numerous jobs to the ahope workflow using
    configuration options from the .ini file. The following executables are
    currently supported:

    * lalapps_tmpltbank
    * pycbc_geom_nonspin_bank

    Parameters
    ----------
    workflow: Workflow
        An instanced class that manages the constructed workflow.
    science_segs : Keyed dictionary of glue.segmentlist objects
        scienceSegs[ifo] holds the science segments to be analysed for each
        ifo. 
    datafind_outs : AhopeFileList
        The file list containing the datafind files.
    output_dir : path string
        The directory where data products will be placed. 
    tags : list of strings
        If given these tags are used to uniquely name and identify output files
        that would be produced in multiple calls to this function.
    link_to_matchedfltr : boolean, optional (default=True)
        If this option is given, the job valid_times will be altered so that
        there will be one inspiral file for every template bank and they will
        cover the same time span. Note that this option must also be given
        during matched-filter generation to be meaningful.

    Returns
    --------
    AhopeOutFileList
        The AhopeOutFileList holding the details of all the template bank jobs.
    '''
    cp = workflow.cp
    # Need to get the exe to figure out what sections are analysed, what is
    # discarded etc. This should *not* be hardcoded, so using a new executable
    # will require a bit of effort here .... 

    ifos = science_segs.keys()
    tmplt_bank_exe = os.path.basename(cp.get('executables','tmpltbank'))
    # Select the appropriate class
    exe_instance = select_tmpltbankjob_instance(tmplt_bank_exe,'tmpltbank')

    # The exe instance needs to know what data segments are analysed, what is
    # discarded etc. This should *not* be hardcoded, so using a new executable
    # will require a bit of effort here .... 

    if link_to_matchedfltr:
        # Use this to ensure that inspiral and tmpltbank jobs overlap. This
        # means that there will be 1 inspiral job for every 1 tmpltbank and
        # the data read in by both will overlap as much as possible. (If you
        # ask the template bank jobs to use 2000s of data for PSD estimation
        # and the matched-filter jobs to use 4000s, you will end up with
        # twice as many matched-filter jobs that still use 4000s to estimate a
        # PSD but then only generate triggers in the 2000s of data that the
        # template bank jobs ran on.
        tmpltbank_exe = os.path.basename(cp.get('executables', 'inspiral'))
        link_exe_instance = select_matchedfilterjob_instance(tmpltbank_exe, 
                                                            'inspiral')
    else:
        link_exe_instance = None

    # Set up class for holding the banks
    tmplt_banks = AhopeFileList([])

    # Template banks are independent for different ifos, but might not be!
    # Begin with independent case and add after FIXME
    for ifo in ifos:
        job_instance = exe_instance.create_job(workflow.cp, ifo, output_dir,
                                               tags=tags)
        if link_exe_instance:
            link_job_instance = link_exe_instance.create_job(cp, ifo, \
                        output_dir, tags=tags)
        else:
            link_job_instance = None
        sngl_ifo_job_setup(workflow, ifo, tmplt_banks, job_instance, 
                           science_segs[ifo], datafind_outs, output_dir,
                           link_job_instance=link_job_instance, 
                           allow_overlap=True)
    return tmplt_banks

def setup_tmpltbank_without_frames(workflow, output_dir,
                                   tags=[], independent_ifos=False):
    '''
    Setup ahope workflow to use a template bank (or banks) that are generated in
    the workflow, but do not use the data to estimate a PSD, and therefore do
    not vary over the duration of the workflow. This can either generate one
    bank that is valid for all ifos at all times, or multiple banks that are
    valid only for a single ifo at all times (one bank per ifo).

    Parameters
    ----------
    workflow: Workflow
        An instanced class that manages the constructed workflow.
    output_dir : path string
        The directory where the template bank outputs will be placed. 
    tags : list of strings
        If given these tags are used to uniquely name and identify output files
        that would be produced in multiple calls to this function.
    independent_ifos : Boolean, optional (default=False)
        If given this will produce one template bank per ifo. If not given
        there will be on template bank to cover all ifos.

    Returns
    --------
    AhopeFileList
        The AhopeFileList holding the details of the template bank(s).
    '''
    cp = workflow.cp
    # Need to get the exe to figure out what sections are analysed, what is
    # discarded etc. This should *not* be hardcoded, so using a new executable
    # will require a bit of effort here .... 

    ifos = workflow.ifos
    fullSegment = workflow.analysis_time

    tmplt_bank_exe = os.path.basename(cp.get('executables','tmpltbank'))
    # Can not use lalapps_template bank with this
    if tmplt_bank_exe == 'lalapps_tmpltbank':
        errMsg = "Lalapps_tmpltbank cannot be used to generate template banks "
        errMsg += "without using frames. Try another code."
        raise ValueError(errMsg)

    # Select the appropriate class
    exe_instance = select_tmpltbankjob_instance(tmplt_bank_exe,'tmpltbank')

    tmplt_banks = AhopeFileList([])

    # Make the distinction between one bank for all ifos and one bank per ifo
    if independent_ifos:
        ifoList = [ifo for ifo in ifos]
    else:
        ifoList = [''.join(ifos)]

    for ifo in ifoList:
        job_instance = exe_instance.create_job(workflow.cp, ifo, output_dir,
                                               tags=tags)
        node = job_instance.create_nodata_node(fullSegment)
        workflow.add_node(node)
        tmplt_banks += node.output_files
        
    return tmplt_banks

def setup_tmpltbank_pregenerated(workflow, tags=[]):
    '''
    Setup ahope workflow to use a pregenerated template bank.
    The bank given in cp.get('ahope','pregenerated-template-bank') will be used
    as the input file for all matched-filtering jobs. If this option is
    present, ahope will assume that it should be used and not generate
    template banks within the workflow.

    Parameters
    ----------
    workflow: Workflow
        An instanced class that manages the constructed workflow.
    tags : list of strings
        If given these tags are used to uniquely name and identify output files
        that would be produced in multiple calls to this function.

    Returns
    --------
    AhopeFileList
        The AhopeFileList holding the details of the template bank.
    '''
    # Currently this uses the *same* fixed bank for all ifos.
    # Maybe we want to add capability to analyse separate banks in all ifos?
    
    # Set up class for holding the banks
    tmpltBanks = AhopeFileList([])

    cp = workflow.cp
    pre_gen_bank = cp.get_opt_tags('ahope','tmpltbank-pregenerated-bank', tags)
    global_seg = workflow.analysis_time

    for ifo in workflow.ifos:
        # Add bank for that ifo
        user_tag = "PREGEN_TMPLTBANK"
        file_url = urlparse.urljoin('file:', urllib.pathname2url(pre_gen_bank))
        curr_file = AhopeFile(ifo, user_tag, global_seg, file_url, tags=tags)
        tmplt_banks.append(curr_file)
        
    return tmplt_banks


from __future__ import division

import os
import urlparse, urllib
import logging
from glue import segments
from pycbc.ahope.ahope_utils import *
from pycbc.ahope.jobsetup_utils import *

def setup_tmpltbank_workflow(workflow, science_segs, 
                             datafind_outs, output_dir):
    '''
    Setup template bank section of ahope workflow. This function is responsible
    for deciding which of the various template bank workflow generation
    utilities should be used. Currently the logic is as follows:
    
    * If pregenerated-template-bank=BANK option in [ahope] section, use
      setup_tmpltbank_pregenerated. This will assume a pregenerated bank called
      BANK is to be used for **all** ahope matched-filtering.

    * Otherwise use setup_tmpltbank_dax_generated. This will assume that the
      template banks are to be generated within the workflow. This will
      generate numerous banks for every ifo, dependent on configuration
      options.

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

    Returns
    --------
    AhopeOutFileList
        The AhopeOutFileList holding the details of all the template bank jobs.
    '''
    logging.info("Entering template bank generation module.")
    cp = workflow.cp
    
    # There should be a number of different options here, for e.g. to set
    # up fixed bank, or maybe something else
    
    # First thing is to check if a pre-generated bank is supplied:
    if (cp.has_option('ahope','pregenerated-template-bank')):
        logging.info("Setting template bank from pre-generated bank(s).")
        tmplt_banks = setup_tmpltbank_pregenerated(cp, science_segs.keys())
    # Else we assume template banks will be generated in the workflow
    else:
        logging.info("Adding template bank jobs to workflow.")
        tmplt_banks = setup_tmpltbank_dax_generated(workflow, science_segs,
                                                    datafind_outs, output_dir)
    
    logging.info("Leaving template bank generation module.")
    return tmplt_banks

def setup_tmpltbank_dax_generated(workflow, science_segs, datafind_outs,
                                  output_dir, link_to_matchedfltr=True):
    '''
    Setup template bank jobs that are generated as part of the ahope workflow.
    This function will add numerous jobs to the ahope workflow using
    configuration options from the .ini file. The following executables are
    currently supported:

    * lalapps_tmpltbank

    Parameters
    ----------
    cp : ConfigParser
        The ConfigParser holding all the options used by the ahope workflow.
    scienceSegs : Keyed dictionary of glue.segmentlist objects
        scienceSegs[ifo] holds the science segments to be analysed for each
        ifo. 
    ahopeDax : Instanced CondorDag class
        The CondorDag class that will hold all the jobs that the ahope workflow
        needs to run.

    Returns
    --------
    AhopeOutFileList
        The AhopeOutFileList holding the details of all the template bank jobs.
    '''
    cp = workflow.cp
    # Need to get the exe to figure out what sections are analysed, what is
    # discarded etc. This should *not* be hardcoded, so using a new executable
    # will require a bit of effort here .... 
    # There is also a stub for a default class using values given in the .ini
    # file.

    ifos = science_segs.keys()
    tmplt_bank_exe = os.path.basename(cp.get('executables','tmpltbank'))
    # Select the appropriate class
    exe_instance = select_tmpltbankjob_instance(tmplt_bank_exe,'tmpltbank')

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
        sngl_ifo_job_setup(workflow, ifo, tmplt_banks, exe_instance, 
                           science_segs[ifo], datafind_outs, output_dir,
                           link_exe_instance=link_exe_instance, 
                           allow_overlap=True)
    return tmplt_banks

def setup_tmpltbank_pregenerated(cp, ifos):
    '''
    Setup ahope workflow to use a pregenerated template bank.
    The bank given in cp.get('ahope','pregenerated-template-bank') will be used
    as the input file for all matched-filtering jobs. If this option is
    present, ahope will assume that it should be used and not generate
    template banks within the workflow.

    Parameters
    ----------
    cp : ConfigParser
        The ConfigParser holding all the options used by the ahope workflow.
    ifos : list of strings
        The list of ifos that are used in this analysis.

    Returns
    --------
    AhopeOutFileList
        The AhopeOutFileList holding the details of the template bank.
    '''
    # Currently this uses the *same* fixed bank for all ifos.
    # Maybe we want to add capability to analyse separate banks in all ifos?
    
    # Set up class for holding the banks
    tmpltBanks = AhopeFileList([])

    pre_gen_bank = cp.get('ahope','pregenerated-template-bank')
    global_seg = segments.segment([0, 9999999999])

    for ifo in ifos:
        # Add bank for that ifo
        user_tag = "PREGEN_TMPLTBANK"
        file_url = urlparse.urljoin('file:', urllib.pathname2url(pre_gen_bank))
        curr_file = AhopeFile(ifo, user_tag, global_seg, file_url)
        tmplt_banks.append(curr_file)
        
    return tmplt_banks


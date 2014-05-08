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
This module is used to prepare output from the coincidence and/or matched filter
stages of the workflow for post-processing (post-processing = calculating
significance of candidates and making any rates statements). For details of this
module and its capabilities see here:
https://ldas-jobs.ligo.caltech.edu/~cbc/docs/pycbc/NOTYETCREATED.html
"""

from __future__ import division

import os
import os.path
from glue import segments
from pycbc.ahope.ahope_utils import *
from pycbc.ahope.jobsetup_utils import *

def setup_postprocessing(workflow, trigger_files, summary_xml_files,
                         output_dir, tags=[], **kwargs):
    """
    This function aims to be the gateway for running postprocessing in CBC
    offline workflows. Post-processing generally consists of calculating the
    significance of triggers and making any statements about trigger rates.
    Dedicated plotting jobs do not belong here.

    Properties
    -----------
    Workflow : ahope.Workflow
        The ahope workflow instance that the coincidence jobs will be added to.
    trigger_files : ahope.AhopeFileList
        An AhopeFileList of the trigger files that are used as
        input at this stage.
    summary_xml_files : ahope.AhopeFileList
        An AhopeFileList of the output of the analysislogging_utils module.
    output_dir : path
        The directory in which output files will be stored.
    tags : list of strings (optional, default = [])
        A list of the tagging strings that will be used for all jobs created
        by this call to the workflow. An example might be ['POSTPROC1'] or
        ['DENTYSNEWPOSTPROC']. This will be used in output names.

    Returns
    --------
    post_proc_files : ahope.AhopeFileList
        A list of the output from this stage.

    """
    logging.info("Entering post-processing preparation stage.")
    make_analysis_dir(output_dir)

    # Parse for options in .ini file
    post_proc_method = workflow.cp.get_opt_tags("ahope-postproc",
                                        "postproc-method", tags)

    # Scope here for adding different options/methods here. For now we only
    # have the single_stage ihope method which consists of converting the
    # ligolw_thinca output xml into one file, clustering, performing injection
    # finding and putting everything into one SQL database.
    if post_proc_method == "PIPEDOWN_AHOPE":
        # If you want the intermediate output files, call this directly
        post_proc_files = setup_postproc_pipedown_ahope(workflow,
                           trigger_files, summary_xml_files, output_dir,
                           tags=tags, **kwargs)
    else:
        errMsg = "Post-processing method not recognized. Must be "
        errMsg += "one of PIPEDOWN_AHOPE (currently only one option)."
        raise ValueError(errMsg)

    logging.info("Leaving post-processing module.")

    return post_proc_files

def setup_postproc_pipedown_ahope(workflow, trigger_files, summary_xml_files,
                                  output_dir, tags=[], veto_cats=[]):
    """
    This module sets up the post-processing stage in ahope, using a pipedown
    style set up. This consists of running compute_durations to determine and
    store the analaysis time (foreground and background). It then runs cfar
    jobs to determine the false alarm rate for all triggers (simulations or
    otherwise) in the input database.
    Pipedown expects to take as input (at this stage) a single database
    containing all triggers. This sub-module follows that same idea, so
    len(triggerFiles) must equal 1 (for every DQ category that we will run).

    Workflow : ahope.Workflow
        The ahope workflow instance that the coincidence jobs will be added to.
    trigger_files : ahope.AhopeFileList
        An AhopeFileList containing the combined databases at CAT_1,2,3... that
        will be used to calculate FARs
    summary_xml_files : ahope.AhopeFileList
        An AhopeFileList of the output of the analysislogging_utils module.
        For pipedown-style post-processing this should be one file conataing a
        segment table holding the single detector analysed times.
    output_dir : path
        The directory in which output files will be stored.
    tags : list of strings (optional, default = [])
        A list of the tagging strings that will be used for all jobs created
        by this call to the workflow. An example might be ['POSTPROC1'] or
        ['DENTYSNEWPOSTPROC']. This will be used in output names.
    veto_cats : list of integers (optional, default = [])
        Decide which set of veto files should be used in the post-processing
        preparation. This is used, for example, to tell the workflow that you
        are only interested in quoting results at categories 2, 3 and 4. In
        which case just supply [2,3,4] for those veto files here.
   
    Returns
    --------
    final_files : ahope.AhopeFileList
        A list of the final SQL databases containing computed FARs.
    """
    if not veto_cats:
        raise ValueError("Veto cats is required.")
    if not len(summary_xml_files) == 1:
        errMsg = "I need exactly one summaryXML file, got %d." \
                                                     %(len(summary_xml_files),)
        raise ValueError(errMsg)

    # Setup needed exe classes
    compute_durations_exe_tag = workflow.cp.get_opt_tags("ahope-postproc",
                                   "postproc-computedurations-exe", tags)
    compute_durations_exe = select_genericjob_instance(workflow,\
                                                     compute_durations_exe_tag)
    cfar_exe_tag = workflow.cp.get_opt_tags("ahope-postproc",
                                            "postproc-cfar-exe", tags)
    cfar_exe = select_genericjob_instance(workflow, cfar_exe_tag) 

    comp_durations_outs = AhopeFileList([])
    cfar_outs = AhopeFileList([])

    for veto_cat in veto_cats:
        veto_tag = 'CUMULATIVE_CAT_%d' %(veto_cat,)

        trig_input_files = trigger_files.find_output_with_tag(veto_tag)
        if not len(trig_input_files) == 1:
            err_msg = "Did not find exactly 1 database input file."
            raise ValueError(err_msg)

        curr_tags = tags + [veto_tag]

        # Start with compute durations
        compute_durations_job = compute_durations_exe.create_job(workflow.cp,
                        workflow.ifoString, out_dir=output_dir, tags=curr_tags)
        compute_durations_node = compute_durations_job.create_node(\
             workflow.analysis_time, trig_input_files[0], summary_xml_files[0])
        workflow.add_node(compute_durations_node)

        # Node has only one output file
        compute_durations_out = compute_durations_node.output_files[0]
        comp_durations_outs.append(compute_durations_out)

        # Add the calculate FAR (cfar) job
        cfar_job = cfar_exe.create_job(workflow.cp,
                        workflow.ifoString, out_dir=output_dir, tags=curr_tags)
        cfar_node = cfar_job.create_node(workflow.analysis_time,
                                       compute_durations_out)
        workflow.add_node(cfar_node)

        # Node has only one output file
        cfar_out = cfar_node.output_files[0]
        cfar_outs.append(cfar_out)

    return cfar_outs

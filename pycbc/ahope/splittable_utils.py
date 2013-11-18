from __future__ import division

import os
from pycbc.ahope.ahope_utils import * 
from pycbc.ahope.jobsetup_utils import *

def setup_splittable_workflow(cp, ahopeDax, tmpltBanks, outDir):
    '''
    Setup matched filter section of ahope workflow.
    FIXME: ADD MORE DOCUMENTATION
    '''
    # Scope here for choosing different options
    splitTableOuts = setup_splittable_dax_generated(cp, ahopeDax, tmpltBanks,\
                                                    outDir)
    
    return splitTableOuts

def setup_splittable_dax_generated(cp, ahopeDax, tmpltBanks, outDir):
    '''
    Setup matched-filter jobs that are generated as part of the ahope workflow.
    FIXME: ADD MORE DOCUMENTATION
    '''
    
    splittableExe = os.path.basename(cp.get('executables', 'splittable'))
    # Select the appropriate class
    exeInstance = select_splitfilejob_instance(splittableExe, 'splittable')

    # Template banks are independent for different ifos, but might not be!
    # Begin with independent case and add after FIXME
    # FIXME: Do not hardcode value of 2
    return split_outfiles(cp, tmpltBanks, exeInstance, 2, ahopeDax, outDir)

def split_outfiles(cp, inputFileList, exeInstance, numBanks, ahopeDax, outDir):
    """
    Add documentation
    """
    # Set up output structure
    outFileGroups = AhopeOutGroupList([])

    # Set up the condorJob class for the current executable
    currExeJob = exeInstance.create_condorjob(cp, None, outDir)

    for input in inputFileList:
        jobTag = input.description + "_" + exeInstance.exeName.upper()
        currExeNode, outUrlList = exeInstance.create_condornode(\
                                      ahopeDax, currExeJob, numBanks, input)
        outFileGroup = AhopeOutGroup(input.observatory, jobTag, input.segment)
        outFileGroup.set_output(outUrlList, [currExeNode])
        outFileGroups.append(outFileGroup)
    return outFileGroups


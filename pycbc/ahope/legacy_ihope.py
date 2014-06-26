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
This library code contains functions and classes that are used to set up
and add jobs/nodes from legacy lalapps C-code to an ahope workflow.
For details about ahope see here:
https://ldas-jobs.ligo.caltech.edu/~cbc/docs/pycbc/ahope.html
"""

import os, types
import logging
import urlparse
from glue import pipeline
from glue import segments
from ahope_utils import Node, AhopeExecutable, AhopeFile

def legacy_get_valid_times(self):
    """
    Return the length of data that the tmpltbank job will need to read and
    the part of that data that the template bank is valid for. In the case
    of lalapps_tmpltbank the following options are needed to set this up
    and will be used by the AhopeExecutable to figure this out:

    * --pad-data (seconds, amount of data used to pad the analysis region.
      This is needed as some data will be corrupted from the data
      conditioning process)

    * --segment-length (sample points, length of each analysis segment)

    * --sample-rate (Hz, number of sample points per second. The data will
      be resampled to this value if necessary

    * --number-of-segments (Number of analysis segments, note that
      overlapping segments are used for PSD estimation, so every data
      point will appear in two segments, except the first
      segment-length/4 and last segment-length/4 points.)

    Returns
    -------
    dataLength : float (seconds)
        The length of data that the job will need
    validChunk : glue.glue.segments.segment
        The start and end of the dataLength that is valid for the template
        bank.
    """
    # Read in needed options. This will fail if options not present
    # It will search relevant sub-sections for the option, so this can be
    # set differently for each ifo.
    padData = int(self.get_opt('pad-data'))
    segmentLength = float(self.get_opt('segment-length'))
    sampleRate = float(self.get_opt('sample-rate'))
    numSegments = int(self.get_opt('number-of-segments'))
    
    # Calculate total valid duration
    analysisDur = int(segmentLength/sampleRate) * (numSegments + 1)/2
    if (segmentLength % sampleRate):
        errString = "In tmpltbank, when running lalapps_tmpltbank "
        errString += "segment-length must be a multiple of sample-rate."
        raise ValueError(errString)
    # Set the segments
    dataLength = analysisDur + 2*padData
    validStart = padData
    validEnd = analysisDur + padData
    # If this is inspiral we lose segment-length/4 on start and end
    if self.exe_name == 'inspiral':
        # Don't think inspiral will do well if segmentLength/4 is not
        # an integer
        validStart = validStart + int(segmentLength/(sampleRate * 4))
        validEnd = validEnd - int(segmentLength / (sampleRate * 4))
    validChunk = segments.segment([validStart,validEnd])

    return dataLength, validChunk

        
class LegacyAnalysisNode(Node):
    # This is *ONLY* used by legacy codes where ahope cannot directly
    # set the output name. Do not use elsewhere!
    def  set_jobnum_tag(self, num):
        self.add_var_opt('user-tag', num)
        
class LegacyAnalysisAhopeExecutable(AhopeExecutable):
    """
    The class responsible for setting up jobs for legacy lalapps C-code
    Executables.
    """
    def __init__(self, cp, exe_name, universe, ifo=None, tags=[], out_dir=None):
        Job.__init__(self, cp, exe_name, universe, ifo, out_dir, tags=tags)

    def create_node(self, data_seg, valid_seg, parent=None, dfParents=None, tags=[]):
        node = LegacyAnalysisNode(self)
        
        if not dfParents: 
            raise ValueError("%s must be supplied with frame files" 
                              %(self.exe_name))  
        
        pad_data = int(self.get_opt('pad-data'))
        if pad_data is None:
            raise ValueError("The option pad-data is a required option of "
                             "%s. Please check the ini file." % self.exe_name)                                     
          
        node.add_var_opt('gps-start-time', data_seg[0] + pad_data)
        node.add_var_opt('gps-end-time', data_seg[1] - pad_data)   
         
        cache_file = dfParents[0]       
        
        #check the extension       
        extension = '.xml'
        gzipped = self.get_opt('write-compress')
        if gzipped is not None:
            extension += '.gz'
        
        #create the output file for this job 
        out_file = AhopeFile(self.ifo, self.exe_name, valid_seg,
                             extension=extension,
                             directory=self.out_dir,
                             tags=self.tags + tags)
 
        node.add_output(out_file, opt='output-file')
        node.add_input_list(dfParents, opt='frame-files', delimiter=' ')
        return node

    get_valid_times = legacy_get_valid_times
        
class LegacyInspiralAhopeExecutable(LegacyAnalysisAhopeExecutable):
    """
    The class responsible for setting up jobs for legacy lalapps_inspiral
    AhopeExecutable.
    """
    def __init__(self, cp, exe_name, universe, ifo=None, injection_file=None, 
                       out_dir=None, tags=[]):
        LegacyAnalysisJob.__init__(self, cp, exe_name, universe, ifo, 
                                    out_dir=out_dir, tags=tags)
        self.injection_file = injection_file 

    def create_node(self, data_seg, valid_seg, parent=None, dfParents=None, tags=[]):
        node = LegacyAnalysisAhopeExecutable.create_node(self, data_seg, valid_seg, 
                                                   parent, dfParents, tags=tags)
        node.add_var_opt('trig-start-time', valid_seg[0])
        node.add_var_opt('trig-end-time', valid_seg[1])  
        node.add_input(parent, opt='bank-file')    
        
        if self.injection_file is not None:
            node.add_input(self.injection_file, 'injection-file')
        return node


class LegacySplitBankAhopeExecutable(AhopeExecutable):    
    """
    The class responsible for creating jobs for lalapps_splitbank.
    """
    def __init__(self, cp, exe_name, universe, numBanks,
                 ifo=None, out_dir=None, tags=[]):
        Job.__init__(self, cp, exe_name, universe, ifo, out_dir, tags=tags)
        self.num_banks = int(numBanks)
        tmpNumBanks = self.get_opt("number-of-banks")
        if tmpNumBanks:
            # Option is in ini file, check it agrees
            if not int(tmpNumBanks) == self.num_banks:
                errMsg = "Number of banks provided in [ahope-splitbank] "
                errMsg += "section does not agree with value given in the "
                errMsg += "[%s] section of the ini file. " %(exe_name)
                raise ValueError(errMsg)
        else:
            # Option not given, so add it
           self.add_opt("number-of-banks", self.num_banks)
            

    def create_node(self, bank):
        """
        Set up a CondorDagmanNode class to run lalapps_splitbank code

        Parameters
        ----------
        bank : AhopeOutFile 
            The AhopeOutFile containing the template bank to be split

        Returns
        --------
        node : Node
            The node to run the job
        """
        node = Node(self)
        # FIXME: This is a hack because SplitBank fails if given an input file
        # whose path contains the character '-' or if the input file is not in
        # the same directory as the output. Therefore we just set the path to
        # be the local path
        fullPath = bank.cache_entry.path
        bank.cache_entry.path = os.path.basename(fullPath)
        node.add_input(bank, opt='bank-file')
        # FIXME: Set the path back to what it was. This is part of the hack
        #        above and should be removed if possible.
        bank.cache_entry.path = fullPath
        
        # Get the output (taken from inspiral.py)
        url_list = []
        x = bank.filename.split('-')
        if len(x) != 4:
            errMsg = "Input file name is not compatible with splitbank. Name "
            errMsg += "must follow the lal cache standard, for example "
            errMsg += "H1-TMPLTBANK-900000000-1000.xml. "
            errMsg += "Got %s." %(bank.filename,)
            raise ValueError(errMsg)
        for i in range( 0, self.num_banks):
            out_file = "%s-%s_%2.2d-%s-%s" %(x[0], x[1], i, x[2], x[3])
            out_url = urlparse.urlunparse(['file', 'localhost',
                                          os.path.join(self.out_dir, out_file),
                                          None, None, None])
            url_list.append(out_url)
                
            job_tag = bank.description + "_" + self.exe_name.upper()
            out_file = AhopeFile(bank.ifo, job_tag, bank.segment, 
                                   file_url=out_url, tags=bank.tags)
            node.add_output(out_file)
        return node


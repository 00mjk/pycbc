# Copyright (C) 2013  Ian Harry, Alex Nitz
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
This module provides the worker functions and classes that are used when
creating an ahope workflow. For details about ahope see here:
https://ldas-jobs.ligo.caltech.edu/~cbc/docs/pycbc/ahope.html
"""

import Pegasus.DAX3 as dax
import os, sys, subprocess, logging, math, string, urlparse, ConfigParser
import numpy
from itertools import combinations
from os.path import splitext, basename, isfile
import lal as lalswig
from glue import lal
from glue import segments, pipeline
from configparserutils import AhopeConfigParser
import pylal.dq.dqSegmentUtils as dqUtils
from pycbc.workflow.workflow import Workflow, Node, File, Executable
import copy

# Ahope should never be using the glue LIGOTimeGPS class, override this with
# the nice SWIG-wrapped class in lal
lal.LIGOTimeGPS = lalswig.LIGOTimeGPS

#REMOVE THESE FUNCTIONS  FOR PYTHON >= 2.7 ####################################
def check_output(*popenargs, **kwargs):
    """
    This function is used to obtain the stdout of a command. It is only used
    internally, recommend using the make_external_call command if you want
    to call external executables.
    """
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    process = subprocess.Popen(stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    return output

###############################################################################

def make_analysis_dir(path):
    """
    Make the analysis directory path, any parent directories that don't already
    exist, and the 'logs' subdirectory of path.
    """
    if path is not None:
        makedir(os.path.join(path, 'logs'))

def makedir(path):
    """
    Make the analysis directory path and any parent directories that don't
    already exist. Will do nothing if path already exists.
    """
    if not os.path.exists(path) and path is not None:
        os.makedirs(path)

def is_condor_exec(exe_path):
    """
    Determine if an executable is condor-compiled

    Parameters
    ----------
    exe_path : str
          The executable path

    Returns
    -------
    truth_value  : boolean
        Return True if the exe is condor compiled, False otherwise.
    """
    if check_output(['nm', '-a', exe_path]).find('condor') != -1:
        return True
    else:
        return False
        
class AhopeExecutable(Executable):
    def __init__(self, cp, name, 
                       universe=None, ifo=None, out_dir=None, tags=[]):
        """
        Initialize the AhopeExecutable class.

        Parameters
        -----------
        cp : ConfigParser object
            The ConfigParser object holding the ahope configuration settings
        exec_name : string
            Executable name
        universe : string, optional
            Condor universe to run the job in
        ifo: string, optional
        out_dir: path, optional
            The folder to store output files of this job. 
        tags : list of strings
            A list of strings that is used to identify this job.
        """
        Executable.__init__(self, name)
        
        tags = [tag.upper() for tag in tags]
        self.tags = tags
        self.ifo = ifo
        self.cp = cp
        self.universe=universe
        
        # Determine the output directory
        if out_dir is not None:
            self.out_dir = out_dir
        elif len(tags) == 0:
            self.out_dir = name
        else:
            self.out_dir = "%s-%s" % (name, '_'.join(tags))            
        if not os.path.isabs(self.out_dir):
            self.out_dir = os.path.join(os.getcwd(), self.out_dir) 
              
        # Check that the executable actually exists locally
        exe_path = cp.get('executables', name)
        if os.path.isfile(exe_path):
            logging.debug("Using %s executable "
                          "at %s" % (exe_name, exe_path))
        else:
            raise TypeError("Failed to find %s executable " 
                            "at %s" % (name, exe_path))
        
        self.add_pfn(exe_path)

        # Determine the condor universe if we aren't given one 
        if self.universe is None:
            if is_condor_exec(exe_path):
                self.universe = 'standard'
            else:
                self.universe = 'vanilla'
                
        logging.debug("%s executable will run as %s universe"
                     % (name, self.universe))  
    
        # Determine the sections from the ini file that will configure
        # this executable
        sections = [self.name]
        for tag in tags:
             section = '%s-%s' %(self.name, tag.lower())
             if cp.has_section(section):
                sections.append(section)
        self.sections = sections   
        # Do some basic sanity checking on the options      
        for sec1, sec2 in combinations(sections, 2):
            cp.check_duplicate_options(sec1, sec2, raise_error=True)
             
        # collect the options from the ini file section(s)
        self.common_options = []        
        for sec in sections:
            if cp.has_section(sec):
                self.add_ini_opts(cp, sec)
            else:
                warnString = "warning: config file is missing section [%s]"\
                             %(sec,)
                logging.warn(warnString)
                
    def add_ini_opts(self, cp, sec):
        for opt in cp.options(sec):
            value = string.strip(cp.get(sec, opt))
            self.common_options += ['--%s' % opt, value]
            
    def add_opt(self, opt, value=None):
        if value is None:
            self.common_options += [opt]
        else:
            self.common_options += [opt, value]
            
    def get_opt(self, opt):
        for sec in self.sections:
            try:
                key = self.cp.get(sec, opt)
                if key:
                    return key
            except ConfigParser.NoOptionError:
                pass
        
        return None

class AhopeWorkflow(Workflow):
    """
    This class manages an aHOPE style workflow. It provides convenience 
    functions for finding input files using time and keywords. It can also
    generate cache files from the inputs. It makes heavy use of the
    pipeline.CondorDAG class, which is instantiated under self.dag.
    """
    def __init__(self, args, name):
        """
        Create an aHOPE workflow
        
        Parameters
        ----------
        args : argparse.ArgumentParser
            The command line options to initialize an ahope workflow.
        """
        Workflow.__init__(self, name)
        
        # Parse ini file
        self.cp = AhopeConfigParser.from_args(args)
        
        # Dump the parsed config file
        ini_file = os.path.abspath(self.name + '_parsed.ini')
        if not os.path.isfile(ini_file):
            fp = open(ini_file, 'w')
            self.cp.write(fp)
            fp.close()
        else:
            logging.warn("Cowardly refusing to overwrite %s." %(ini_file))

        # Set global values
        start_time = int(self.cp.get("ahope", "start-time"))
        end_time = int(self.cp.get("ahope", "end-time"))
        self.analysis_time = segments.segment([start_time, end_time])

        # Set the ifos to analyse
        ifos = []
        for ifo in self.cp.options('ahope-ifos'):
            ifos.append(ifo.upper())
        self.ifos = ifos
        self.ifos.sort(key=str.lower)
        self.ifo_string = ''.join(self.ifos)
        
        # Set up input and output file lists for workflow
        self._inputs = AhopeFileList([])
        self._outputs = AhopeFileList([])
         
    def execute_node(self, node):
        """ Execute this node immediately on the local site and place its
        inputs and outputs into the workflow data lists. 
        """
        node.executed = True
        cmd_list = node.get_command_line()
        
        # Must execute in output directory.
        curr_dir = os.getcwd()
        out_dir = node.executable.out_dir
        os.chdir(out_dir)
        
        # Make call
        make_external_call(cmd_list, out_dir=os.path.join(out_dir, 'logs'),
                                     out_basename=node.executable.name) 
        # Change back
        os.chdir(curr_dir)
        
        self._inputs += node._outputs
        
        for fil in node._outputs:
            fil.node = None
            
    def save(self):
        # add executable pfns for local site to dax
        for exe in self._executables:
            exe.insert_into_dax(self._adag)
            
        # add workflow input files pfns for local site to dax
        for fil in self._inputs:
            fil.insert_into_dax(self._adag)
            
        # save the dax file
        Workflow.save(self, self.name + '.dax')
        
        # add workflow storage locations to the output mapper
        f = open(self.name + '.map', 'w')
        for out in self._outputs:
            f.write(out.output_map_str() + '\n')
    
class AhopeNode(Node):
    def __init__(self, executable):
        Node.__init__(self, executable)
        self.executed = False
        self.set_category(executable.name)
        
        # Set default requirements for a AhopeNode
        self.set_memory(1000)
        self.set_storage(100)
        
        if executable.universe == 'vanilla':
            self.add_profile('condor', 'getenv', 'True')
            
        self._options += self.executable.common_options
    
    def get_command_line(self):
        self._finalize()
        arglist = self._dax_node.arguments
        
        tmpargs = []
        for a in arglist:
            if not isinstance(a, AhopeFile):
                tmpargs += a.split(' ')
            else:
                tmpargs.append(a)
        arglist = tmpargs
        
        arglist = [a for a in arglist if a != '']
        
        arglist = [a.storage_path if isinstance(a, AhopeFile) else a for a in arglist]
                        
        exe_path = urlparse.urlsplit(self.executable.get_pfn()).path
        return [exe_path] + arglist
        
    def new_output_file_opt(self, valid_seg, extension, option_name, tags=[]):
        """
        This function will create a AhopeFile corresponding to the given
        information and then add that file as output of this node.

        Parameters
        -----------
        valid_seg : glue.segments.segment
            The time span over which the job is valid for.
        extension : string
            The extension to be used at the end of the filename. 
            E.g. '.xml' or '.sqlite'.
        option_name : string
            The option that is used when setting this job as output. For e.g.
            'output-name' or 'output-file', whatever is appropriate for the
            current executable.
        tags : list of strings, (optional, default=[])
            These tags will be added to the list of tags already associated with
            the job. They can be used to uniquely identify this output file.
        """
        
        # Changing this from set(tags) to enforce order. It might make sense
        # for all jobs to have file names with tags in the same order.
        all_tags = copy.deepcopy(self.executable.tags)
        for tag in tags:
            if tag not in all_tags:
                all_tags.append(tag)

        fil = AhopeFile(self.executable.ifo, self.executable.name, valid_seg, 
                         extension=extension, 
                         directory=self.executable.out_dir, tags=all_tags)    
        self.add_output_opt(option_name, fil)
        
    @property    
    def output_files(self):
        return self._outputs
    
class AhopeFile(File):
    '''
    This class holds the details of an individual output file 
    This file(s) may be pre-supplied, generated from within the ahope
    command line script, or generated within the workflow. The important stuff
    is:

    * The ifo that the AhopeFile is valid for
    * The time span that the AhopeOutFile is valid for
    * A short description of what the file is
    * The extension that the file should have
    * The url where the file should be located

    An example of initiating this class:
    
    c = AhopeFile("H1", "INSPIRAL_S6LOWMASS", segments.segment(815901601, 815902001), file_url="file://localhost/home/spxiwh/H1-INSPIRAL_S6LOWMASS-815901601-400.xml.gz" )

    another where the file url is generated from the inputs:

    c = AhopeFile("H1", "INSPIRAL_S6LOWMASS", segments.segment(815901601, 815902001), directory="/home/spxiwh", extension="xml.gz" )
    '''
    def __init__(self, ifos, exe_name, segs, file_url=None, 
                 extension=None, directory=None, tags=None):       
        """
        Create an AhopeFile instance
        
        Parameters
        ----------
        ifos : string or list
            The ifo(s) that the AhopeFile is valid for. If the file is
            independently valid for multiple ifos it can be provided as a list.
            Ie. ['H1',L1','V1'], if the file is only valid for the combination
            of ifos (for e.g. ligolw_thinca output) then this can be supplied
            as, for e.g. "H1L1V1".
        exe_name: string
            A short description of the executable description, tagging
            only the program that ran this job.
        segs : glue.segment or glue.segmentlist
            The time span that the AhopeOutFile is valid for. Note that this is
            *not* the same as the data that the job that made the file reads in.
            Lalapps_inspiral jobs do not analyse the first an last 72s of the
            data that is read, and are therefore not valid at those times. If
            the time is not continuous a segmentlist can be supplied.
        file_url : url (optional, default=None)
            If this is *not* supplied, extension and directory must be given.
            If specified this explicitly points to the url of the file, or the
            url where the file will be generated when made in the workflow.
        extension : string (optional, default=None)
            Either supply this *and* directory *or* supply only file_url.
            If given this gives the extension at the end of the file name. The
            full file name will be inferred from the other arguments
            following the ahope standard.
        directory : string (optional, default=None)
            Either supply this *and* extension *or* supply only file_url.
            If given this gives the directory in which the file exists, or will
            exists. The file name will be inferred from the other arguments
            following the ahope standard.
        tags : list of strings (optional, default=None)
            This is a list of descriptors describing what this file is. For
            e.g. this might be ["BNSINJECTIONS" ,"LOWMASS","CAT_2_VETO"].
            These are used in file naming.
        """
        
        # Set the science metadata on the file
        if isinstance(ifos, (str, unicode)):
            self.ifo_list = [ifos]
        else:
            self.ifo_list = ifos
        self.ifo_string = ''.join(self.ifo_list)
        self.description = exe_name
        
        if isinstance(segs, (segments.segment)):
            self.segment_list = segments.segmentlist([segs])
        elif isinstance(segs, (segments.segmentlist)):
            self.segment_list = segs
        else:
            err = "segs input must be either glue.segments.segment or "
            err += "segments.segmentlist. Got %s." %(str(type(segs)),)
            raise ValueError(err)
            
        self.tags = tags 
        if tags is not None:
            self.tag_str = '_'.join(tags)
            tagged_description = '_'.join([self.description] + tags)
        else:
            tagged_description = self.description
            
        # Follow the capitals-for-naming convention
        self.ifo_string = self.ifo_string.upper()
        self.tagged_description = tagged_description.upper()
      
        if not file_url:
            if not extension:
                raise TypeError("a file extension required if a file_url "
                                "is not provided")
            if not directory:
                raise TypeError("a directory is required if a file_url is "
                                "not provided")
            
            filename = self._filename(self.ifo_string, self.tagged_description,
                                      extension, self.segment_list.extent())
            path = os.path.join(directory, filename)
            if not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path) 
            file_url = urlparse.urlunparse(['file', 'localhost', path, None,
                                            None, None])
       
        self.cache_entry = lal.CacheEntry(self.ifo_string,
                   self.tagged_description, self.segment_list.extent(), file_url)
        self.cache_entry.ahope_file = self

        File.__init__(self, basename(self.cache_entry.path))
        self.storage_path = self.cache_entry.path

    @property
    def ifo(self):
        """
        If only one ifo in the ifo_list this will be that ifo. Otherwise an
        error is raised.
        """
        if len(self.ifo_list) == 1:
            return self.ifo_list[0]
        else:
            err = "self.ifo_list must contain only one ifo to access the "
            err += "ifo property. %s." %(str(self.ifo_list),)
            raise TypeError(err)

    @property
    def segment(self):
        """
        If only one segment in the segmentlist this will be that segment.
        Otherwise an error is raised.
        """
        if len(self.segment_list) == 1:
            return self.segment_list[0]
        else:
            err = "self.segment_list must only contain one segment to access"
            err += " the segment property. %s." %(str(self.segment_list),)
            raise TypeError(err)
        
    def _filename(self, ifo, description, extension, segment):
        """
        Construct the standard output filename. Should only be used internally
        of the AhopeFile class.
        """        
        if extension.startswith('.'):
            extension = extension[1:]
            
        # Follow the frame convention of using integer filenames,
        # but stretching to cover partially covered seconds.
        start = int(segment[0])
        end = int(math.ceil(segment[1]))
        duration = str(end-start)
        start = str(start)
        
        return "%s-%s-%s-%s.%s" % (ifo, description.upper(), start, 
                                   duration, extension)  
    
class AhopeFileList(list):
    '''
    This class holds a list of AhopeFile objects. It inherits from the
    built-in list class, but also allows a number of features. ONLY
    AhopeFile instances should be within an AhopeFileList instance.
    '''
    entry_class = AhopeFile

    def find_output(self, ifo, time):
        '''
        Return one AhopeFile that covers the given time, or is most
        appropriate for the supplied time range.

        Parameters
        -----------
        ifo : string
           Name of the ifo (or ifos) that the file should be valid for.
        time : int/float/LIGOGPStime or tuple containing two values
           If int/float/LIGOGPStime (or similar may of specifying one time) is
           given, return the AhopeFile corresponding to the time. This calls
           self.find_output_at_time(ifo,time).
           If a tuple of two values is given, return the AhopeFile that is
           **most appropriate** for the time range given. This calls
           self.find_output_in_range

        Returns
        --------
        AhopeFile class
           The AhopeFile that corresponds to the time/time range
        '''
        # Determine whether I have a specific time, or a range of times
        try:
            lenTime = len(time)
        except TypeError:
            # This is if I have a single time
            outFile = self.find_output_at_time(ifo,time)                
        else:
            # This is if I have a range of times
            if lenTime == 2:
                outFile = self.find_output_in_range(ifo,time[0],time[1])
            # This is if I got a list that had more (or less) than 2 entries
            if len(time) != 2:
                raise TypeError("I do not understand the input variable time")
        return outFile

    def find_output_at_time(self, ifo, time):
       '''
       Return AhopeFile that covers the given time.

        Parameters
        -----------
        ifo : string
           Name of the ifo (or ifos) that the AhopeFile should correspond to
        time : int/float/LIGOGPStime
           Return the AhopeFiles that covers the supplied time. If no
           AhopeFile covers the time this will return None.

        Returns
        --------
        list of AhopeFile classes
           The AhopeFiles that corresponds to the time.
        '''
       # Get list of AhopeFiles that overlap time, for given ifo
       outFiles = [i for i in self if ifo in i.ifo_list and time in i.segment_list] 
       if len(outFiles) == 0:
           # No AhopeOutFile at this time
           return None
       elif len(outFiles) == 1:
           # 1 AhopeOutFile at this time (good!)
           return outFiles
       else:
           # Multiple output files. Currently this is valid, but we may want
           # to demand exclusivity later, or in certain cases. Hence the
           # separation.
           return outFiles

    def find_outputs_in_range(self, ifo, current_segment, useSplitLists=False):
        """
        Return the list of AhopeFiles that is most appropriate for the supplied
        time range. That is, the AhopeFiles whose coverage time has the
        largest overlap with the supplied time range.

        Parameters
        -----------
        ifo : string
           Name of the ifo (or ifos) that the AhopeFile should correspond to
        current_segment : glue.segment.segment
           The segment of time that files must intersect.

        Returns
        --------
        AhopeFileList class
           The list of AhopeFiles that are most appropriate for the time range
        """
        currsegment_list = segments.segmentlist([current_segment])

        # Get all files overlapping the window
        overlap_files = self.find_all_output_in_range(ifo, current_segment,
                                                    useSplitLists=useSplitLists)

        # By how much do they overlap?
        overlap_windows = [abs(i.segment_list & currsegment_list) for i in overlap_files]

        # FIXME: Error handling for the overlap_files == [] case?

        # Return the AhopeFile with the biggest overlap
        # Note if two AhopeFile have identical overlap, the first is used
        # to define the valid segment
        overlap_windows = numpy.array(overlap_windows, dtype = int)
        segmentLst = overlap_files[overlap_windows.argmax()].segment_list
        
        # Get all output files with the exact same segment definition
        output_files = [f for f in overlap_files if f.segment_list==segmentLst]
        return output_files

    def find_output_in_range(self, ifo, start, end):
        '''
        Return the AhopeFile that is most appropriate for the supplied
        time range. That is, the AhopeFile whose coverage time has the
        largest overlap with the supplied time range. If no AhopeFiles
        overlap the supplied time window, will return None. 

        Parameters
        -----------
        ifo : string
           Name of the ifo (or ifos) that the AhopeFile should correspond to
        start : int/float/LIGOGPStime 
           The start of the time range of interest.
        end : int/float/LIGOGPStime
           The end of the time range of interest

        Returns
        --------
        AhopeFile class
           The AhopeFile that is most appropriate for the time range
        '''
        currsegment_list = segments.segmentlist([current_segment])

        # First filter AhopeFiles corresponding to ifo
        outFiles = [i for i in self if ifo in i.ifo_list]

        if len(outFiles) == 0:
            # No AhopeOutFiles correspond to that ifo
            return None
        # Filter AhopeOutFiles to those overlapping the given window
        currSeg = segments.segment([start,end])
        outFiles = [i for i in outFiles \
                                  if i.segment_list.intersects_segment(currSeg)]

        if len(outFiles) == 0:
            # No AhopeOutFile overlap that time period
            return None
        elif len(outFiles) == 1:
            # One AhopeOutFile overlaps that period
            return outFiles[0]
        else:
            overlap_windows = [abs(i.segment_list & currsegment_list) \
                                                        for i in outFiles]
            # Return the AhopeFile with the biggest overlap
            # Note if two AhopeFile have identical overlap, this will return
            # the first AhopeFile in the list
            overlap_windows = numpy.array(overlap_windows, dtype = int)
            return outFiles[overlap_windows.argmax()]

    def find_all_output_in_range(self, ifo, currSeg, useSplitLists=False):
        """
        Return all files that overlap the specified segment.
        """
        if not useSplitLists:
            # Slower, but simpler method
            outFiles = [i for i in self if ifo in i.ifo_list]
            outFiles = [i for i in outFiles \
                                      if i.segment_list.intersects_segment(currSeg)]
        else:
            # Faster, but more complicated
            # Basically only check if a subset of files intersects_segment by
            # using a presorted list. Sorting only happens once.
            if not self._check_split_list_validity():
                # FIXME: DO NOT hard code this.
                self._temporal_split_list(100)
            startIdx = int( (currSeg[0] - self._splitListsStart) / \
                                                          self._splitListsStep )
            # Add some small rounding here
            endIdx = (currSeg[1] - self._splitListsStart) / self._splitListsStep
            endIdx = int(endIdx - 0.000001)

            outFiles = []
            for idx in range(startIdx, endIdx + 1):
                outFilesTemp = [i for i in self._splitLists[idx] \
                                                            if ifo in i.ifo_list]
                outFiles.extend([i for i in outFilesTemp \
                                      if i.segment_list.intersects_segment(currSeg)])
                # Remove duplicates
                outFiles = list(set(outFiles))

        return self.__class__(outFiles)

    def find_output_with_tag(self, tag):
        """
        Find all files who have tag in self.tags
        """
        # Enforce upper case
        tag = tag.upper()
        return AhopeFileList([i for i in self if tag in i.tags])

    def find_output_with_ifo(self, ifo):
        """
        Find all files who have ifo = ifo
        """
        # Enforce upper case
        ifo = ifo.upper()
        return AhopeFileList([i for i in self if ifo in i.ifo_list])

    def get_times_covered_by_files(self):
        """
        Find the coalesced intersection of the segments of all files in the
        list.
        """
        times = segments.segmentlist([])
        for entry in self:
            times.extend(entry.segment_list)
        times.coalesce()
        return times

    def convert_to_lal_cache(self):
        """
        Return all files in this object as a lal.Cache object
        """
        lalCache = lal.Cache([])
        for entry in self:
            lalCache.append(entry.cache_entry)
        return lalCache

    def _temporal_split_list(self,numSubLists):
        """
        This internal function is used to speed the code up in cases where a
        number of operations are being made to determine if files overlap a
        specific time. Normally such operations are done on *all* entries with
        *every* call. However, if we predetermine which files are at which
        times, we can avoid testing *every* file every time.
  
        We therefore create numSubLists distinct and equal length time windows
        equally spaced from the first time entry in the list until the last.
        A list is made for each window and files are added to lists which they
        overlap.
 
        If the list changes it should be captured and these split lists become
        invalid. Currently the testing for this is pretty basic
        """
        # Assume segment lists are coalesced!
        startTime = float( min([i.segment_list[0][0] for i in self]))
        endTime = float( max([i.segment_list[-1][-1] for i in self]))
        step = (endTime - startTime) / float(numSubLists)

        # Set up storage
        self._splitLists = []
        for idx in range(numSubLists):
            self._splitLists.append(AhopeFileList([]))
        
        # Sort the files

        for ix, currFile in enumerate(self):
            segExtent = currFile.segment_list.extent()
            segExtStart = float(segExtent[0])
            segExtEnd = float(segExtent[1])
            startIdx = (segExtent[0] - startTime) / step
            endIdx = (segExtent[1] - startTime) / step
            # Add some small rounding here
            startIdx = int(startIdx - 0.001) 
            endIdx = int(endIdx + 0.001)

            if startIdx < 0:
                startIdx = 0
            if endIdx >= numSubLists:
                endIdx = numSubLists - 1

            for idx in range(startIdx, endIdx + 1):
                self._splitLists[idx].append(currFile)

        # Set information needed to detect changes and to be used elsewhere
        self._splitListsLength = len(self)
        self._splitListsStart = startTime
        self._splitListsEnd = endTime
        self._splitListsStep = step
        self._splitListsSet = True

    def _check_split_list_validity(self):
        """
        See _temporal_split_list above. This function checks if the current
        split lists are still valid.
        """
        # FIXME: Currently very primitive, but needs to be fast
        if not (hasattr(self,"_splitListsSet") and (self._splitListsSet)):
            return False
        elif len(self) != self._splitListsLength:
            return False
        else:
            return True
   
        


class AhopeOutSegFile(AhopeFile):
    '''
    This class inherits from the AhopeFile class, and is designed to store
    ahope output files containing a segment list. This is identical in
    usage to AhopeFile except for an additional kwarg for holding the
    segment list, if it is known at ahope run time.
    '''
    def __init__(self, ifo, description, segment, fileUrl,
                 segment_list=None, **kwargs):
        """
        See AhopeFile.__init__ for a full set of documentation for how to
        call this class. The only thing unique and added to this class is
        the required option timeSeg, as described below:

        Parameters:
        ------------
        ifo : string or list (required)
            See AhopeFile.__init__
        description : string (required)
            See AhopeFile.__init__
        segment : glue.segments.segment or glue.segments.segmentlist
            See AhopeFile.__init__
        fileUrl : string (required)
            See AhopeFile.__init__
            FIXME: This is a kwarg in AhopeFile and should be here as well,
            if this is removed from the explicit arguments it would allow for
            either fileUrls or constructed file names to be used in AhopeFile.
        segment_list : glue.segments.segmentlist (optional, default=None)
            A glue.segments.segmentlist covering the times covered by the
            segmentlist associated with this file. If this is the science time
            or CAT_1 file this will be used to determine analysis time. Can
            be added by setting self.segment_list after initializing an instance of
            the class.

        """
        AhopeFile.__init__(self, ifo, description, segment, fileUrl,
                              **kwargs)
        self.segmentList = segment_list

    def removeShortSciSegs(self, minSegLength):
        """
        Function to remove all science segments
        shorter than a specific length. Also updates the file on disk to remove
        these segments.

        Parameters
        -----------
        minSegLength : int
            Maximum length of science segments. Segments shorter than this will
            be removed.
        """
        newsegment_list = segments.segmentlist()
        for seg in self.segmentList:
            if abs(seg) > minSegLength:
                newsegment_list.append(seg)
        newsegment_list.coalesce()
        self.segmentList = newsegment_list
        self.toSegmentXml()

    def toSegmentXml(self):
        """
        Write the segment list in self.segmentList to the url in self.url.
        """
        filePointer = open(self.storage_path, 'w')
        dqUtils.tosegmentxml(filePointer, self.segmentList)
        filePointer.close()

def make_external_call(cmdList, out_dir=None, out_basename='external_call',
                       shell=False, fail_on_error=True):
    """
    Use this to make an external call using the python subprocess module.
    See the subprocess documentation for more details of how this works.
    http://docs.python.org/2/library/subprocess.html

    Parameters
    -----------
    cmdList : list of strings
        This list of strings contains the command to be run. See the subprocess
        documentation for more details.
    out_dir : string
        If given the stdout and stderr will be redirected to
        os.path.join(out_dir,out_basename+[".err",".out])
        If not given the stdout and stderr will not be recorded
    out_basename : string
        The value of out_basename used to construct the file names used to
        store stderr and stdout. See out_dir for more information.
    shell : boolean, default=False
        This value will be given as the shell kwarg to the subprocess call.
        **WARNING** See the subprocess documentation for details on this
        Kwarg including a warning about a serious security exploit. Do not
        use this unless you are sure it is necessary **and** safe.
    fail_on_error : boolean, default=True
        If set to true an exception will be raised if the external command does
        not return a code of 0. If set to false such failures will be ignored.
        Stderr and Stdout can be stored in either case using the out_dir
        and out_basename options.

    Returns
    --------
    exitCode : int
        The code returned by the process.
    """
    if out_dir:
        outBase = os.path.join(out_dir,out_basename)
        errFile = outBase + '.err'
        errFP = open(errFile, 'w')
        outFile = outBase + '.out'
        outFP = open(outFile, 'w')
        cmdFile = outBase + '.sh'
        cmdFP = open(cmdFile, 'w')
        cmdFP.write(' '.join(cmdList))
        cmdFP.close()
    else:
        errFile = None
        outFile = None
        cmdFile = None
        errFP = None
        outFP = None

    msg = "Making external call %s" %(' '.join(cmdList))
    logging.debug(msg)
    errCode = subprocess.call(cmdList, stderr=errFP, stdout=outFP,\
                              shell=shell)
    if errFP:
        errFP.close()
    if outFP:
        outFP.close()

    if errCode and fail_on_error:
        raise CalledProcessErrorMod(errCode, ' '.join(cmdList), 
                errFile=errFile, outFile=outFile, cmdFile=cmdFile)
    logging.debug("Call successful, or error checking disabled.")

class CalledProcessErrorMod(Exception):
    """
    This exception is raised when subprocess.call returns a non-zero exit code
    and checking has been requested. This should not be accessed by the user
    it is used only within make_external_call.
    """
    def __init__(self, returncode, cmd, errFile=None, outFile=None, 
                 cmdFile=None):
        self.returncode = returncode
        self.cmd = cmd
        self.errFile = errFile
        self.outFile = outFile
        self.cmdFile = cmdFile
    def __str__(self):
        msg = "Command '%s' returned non-zero exit status %d.\n" \
              %(self.cmd, self.returncode)
        if self.errFile:
            msg += "Stderr can be found in %s .\n" %(self.errFile)
        if self.outFile:
            msg += "Stdout can be found in %s .\n" %(self.outFile)
        if self.cmdFile:
            msg += "The failed command has been printed in %s ." %(self.cmdFile)
        return msg
              
def get_full_analysis_chunk(science_segs):
    """
    Function to find the first and last time point contained in the science segments
    and return a single segment spanning that full time.

    Parameters
    -----------
    science_segs : ifo-keyed dictionary of glue.segments.segmentlist instances
        The list of times that are being analysed in this workflow.
    Returns
    --------
    fullSegment : glue.segments.segment
        The segment spanning the first and last time point contained in science_segs.
    """
    extents = [science_segs[ifo].extent() for ifo in science_segs.keys()]
    min, max = extents[0]
    for lo, hi in extents:
        if min > lo:
            min = lo
        if max < hi:
            max = hi
    fullSegment = segments.segment(min, max)
    return fullSegment
        

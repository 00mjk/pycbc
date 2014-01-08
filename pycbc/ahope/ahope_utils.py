import os, sys
import subprocess
import logging
import math
import numpy
import urlparse
from os.path import splitext, basename
from glue import lal
from glue import segments, pipeline
from configparserutils import parse_ahope_ini_file
import pylal.dq.dqSegmentUtils as dqUtils
import copy

class Job(pipeline.AnalysisJob, pipeline.CondorDAGJob):
    def __init__(self, cp, exe_name, universe, ifo=None, out_dir=None):
        """Initialize the LegacyInspiralAnalysisJob class.
   
        Parameters
        -----------
        cp : ConfigParser object
            The ConfigParser object holding the ahope configuration settings
        sections : list of strings
            sections of the ConfigParser that get added to the opts
        exec_name : string
            Executable name
        universe : string
            Condor universe to run the job in
        extension : string
            Extension of the output file. Used to figure out the output file
            name.
        """
        self.exe_name = exe_name
        self.cp = cp
        self.ifo = ifo
        self.out_dir = out_dir
        
        executable = cp.get('executables', exe_name)
        
        pipeline.CondorDAGJob.__init__(self, universe, executable)
        pipeline.AnalysisJob.__init__(self, cp, dax=True)       
        
        if universe == 'vanilla':
            self.add_condor_cmd('getenv', 'True')
        self.add_condor_cmd('copy_to_spool','False')
        
        sections = [self.exe_name]
        if ifo and cp.has_section('%s-%s' %(self.exe_name, ifo.lower())):
             sections.append('%s-%s' %(self.exe_name, ifo.lower()) )
             
        for sec in sections:
            if cp.has_section(sec):
                self.add_ini_opts(cp, sec)
            else:
                warnString = "warning: config file is missing section [%s]"\
                             %(sec,)
                print >>sys.stderr, warnString

        # What would be a better more general logname ?
        logBaseNam = 'logs/%s-$(macrogpsstarttime)' %(exe_name,)
        logBaseNam += '-$(macrogpsendtime)-$(cluster)-$(process)'
        
        if out_dir:
            self.add_condor_cmd("initialdir", out_dir)

        self.set_stdout_file('%s.out' %(logBaseNam,) )
        self.set_stderr_file('%s.err' %(logBaseNam,) )
        if ifo:
            self.set_sub_file('%s-%s.sub' %(ifo, exe_name,) )
        else:
            self.set_sub_file('%s.sub' %(exe_name,) )
    
    def set_ram(self, ram_value):
        """Set the amount of the RAM that this job requires.
        
        Parameters
        ----------
        ram_value: int
              The amount of ram that this job requires in MB.
        """
        self.add_condor_cmd('Requirements', 'Memory >= %d' %(ram_value))
        self.add_condor_cmd('request_memory', '%d' %(ram_value))

    def create_node(self):
        """Create a condor node from this job.
        """
        return Node(self)
        

class Node(pipeline.CondorDAGNode):
    def __init__(self, job):
        pipeline.CondorDAGNode.__init__(self, job)
        self.input_files = AhopeFileList([])
        self.partitioned_input_files = AhopeFileList([])
        self.output_files = AhopeFileList([])
        self.set_category(job.exe_name)
        
    def add_input(self, files, opts=None):
        """Add a file(s) as input to this node. 
        
        Parameters
        ----------
        file : AhopeFile or list of AhopeFiles
            The files that this node needs to run
        opts : string or list of strings, optional
            The command line options that the executable needs
            in order to set the associated file as input.
        """
        # make the input arguments lists
        if not isinstance(files, list):
            files = [files]
            if opts:
                opts = [opts]
        
        # check that the arguments are sane   
        if opts and len(opts) != len(files):
            raise TypeError('An opt must be provided for each file in the list')
        
        # Add the files to the nodes internal lists of input
        for file in files:         
            self.input_files.append(file) 
            # If possible record in the dag the input
            if len(file.paths) == 1:
                self.add_input_file(file.path)  
            # If not, defer untill we can resolve what the actual inputs
            # will be 
            elif len(file.paths) > 1:
                self.partitioned_input_files.append(file)
                if not opts:
                    # What does it mean to get a file group as input?
                    # How would the program know what the files are?
                    raise TypeError('Cannot accept partitioned ahope file as '
                                'input without a corresponding option string.')
                                
            # If the file was created by another node, then make that
            # node a parent of this one
            if file.node:
                if isinstance(file.node, list):
                    for n in file.node:
                        self.add_parent(n)
                else:
                    self.add_parent(file.node)

        if opts:
            for file, opt in zip(files, opts):
                # The argument has to be resolved later
                if len(file.paths) > 1:
                    file.opt = opt
                elif len(file.paths) == 1:
                    self.add_var_opt(opt, file.path)
            
    def add_output(self, files, opts=None): 
        """Add a file(s) as an output to this node. 
        
        Parameters
        ----------
        file : AhopeFile or list of AhopeFiles
            The files that this node generates
        opts : string or list of strings, optional
            The command line options that the executable needs
            in order to set the names of this file.
        """  
        # make input lists 
        if not isinstance(files, list):
            files = [files]
            if opts:
                opts = [opts]
        
        # check sanity of input
        if opts and len(opts) != len(files):
            raise TypeError('An opt must be provided for each file in the list')
         
        # make sure the files know which node creates them   
        for file in files:
            self.output_files.append(file)
            file.node = self
        if opts:
            for file, opt in zip(files, opts):
                file.opt = opt   

class Executable(object):
    """This class is a reprentation of an executable and its capabilities
    """
    def __init__(self, exe_name, universe):
        self.exe_name = exe_name
        self.condor_universe = universe
        
    def create_job(self, cp, ifo=None, out_dir=None):
        return Job(cp, self.exe_name, self.condor_universe, ifo=ifo, out_dir=out_dir)

class Workflow(object):
    """This class manages an aHOPE style workflow. It provides convenience 
    functions for finding input files using time and keywords. It can also
    generate cache files from the inputs.
    """
    def __init__(self, config):
        """Create an aHOPE workflow
        
        Parameters
        ----------
        config : str
             The path of the ahope configuration file.
        """
        # Parse ini file
        self.cp = parse_ahope_ini_file(config)
        self.basename = basename(splitext(config)[0])
        
        # Initialize the dag
        logfile = self.basename + '.log'
        fh = open( logfile, "w" )
        fh.close()
        self.dag = pipeline.CondorDAG(logfile, dax=False)
        self.dag.set_dax_file(self.basename)
        self.dag.set_dag_file(self.basename)
        
    def partition_node(self, node, partitioned_file):
        import time, random, hashlib
    
        opt = partitioned_file.opt
        nodes = []
        for path in partitioned_file.paths:
            new_node = copy.copy(node)
            new_node._CondorDAGNode__parents = node._CondorDAGNode__parents[:]
            new_node._CondorDAGNode__opts = node.get_opts().copy()
            new_node._CondorDAGNode__input_files = node.get_input_files()[:]  
            new_node._CondorDAGNode__output_files = node.get_output_files()[:]          
            # generate the md5 node name
            t = str( long( time.time() * 1000 ) )
            r = str( long( random.random() * 100000000000000000L ) )
            a = str( self.__class__ )
            new_node._CondorDAGNode__name = hashlib.md5(t + r + a).hexdigest()
            new_node._CondorDAGNode__md5name = new_node._CondorDAGNode__name
            
            new_node.add_var_opt(opt, path)
            new_node.add_input_file(path) 
            nodes.append(new_node)     
        return nodes     
        
    def add_node(self, node):
        # copy the node as many times as necessary so all combinations
        # of the input files are exhausted
        part_files = node.partitioned_input_files
        nodes = [node]
        for file in part_files:
            for n in nodes:
                nodes = self.partition_node(n, file)
            
        if len(nodes) > 1:
            for file in node.output_files:
                path_groups, job_num_tags = file.partition_self(len(nodes))
                for n , paths, tag in zip(nodes, path_groups, job_num_tags):  
                    for path in paths:       
                        n.add_output_file(path)                     
                        if hasattr(file, 'opt'):
                            n.add_var_opt(file.opt, path) 
                        elif hasattr(n, 'set_jobnum_tag'):
                            n.set_jobnum_tag(tag)
                        else:
                            raise ValueError('This node does not support'
                                             'partitioned files as input')                                 
                    self.dag.add_node(n)
                file.node = nodes
                
        elif len(nodes) == 1:
            for file in node.output_files:
                for path in file.paths:
                    node.add_output_file(path)
                    if hasattr(file, 'opt'):
                        node.add_var_opt(file.opt, path)  
            self.dag.add_node(node)   
        
    def write_plans(self):
        self.dag.write_sub_files()
        self.dag.write_script()
        self.dag.write_dag()
        #self.dag.write_abstract_dag()

class AhopeFile(object):
    '''This class holds the details of an individual output file in the ahope
    workflow. This file may be pre-supplied, generated from within the ahope
    command line script, or generated within the workflow. This class inherits
    from the glue.lal.CacheEntry class and has all attributes/methods of that
    class. It also adds some additional stuff for ahope. The important stuff
    from both is:

    * The location of the output file (which may not yet exist)
    * The ifo that the AhopeFile is valid for
    * The time span that the AhopeOutFile is valid for
    * A short description of what the file is
    * The dax node that will generate the output file (if appropriate). If the
      file is generated within the workflow the dax job object will hold all
      the job-specific information that may be relevant for later stages.

    An example of initiating this class:
    
    c = AhopeFile("H1", "INSPIRAL_S6LOWMASS", segments.segment(815901601, 815902177.5), "file://localhost/home/kipp/tmp/1/H1-815901601-576.xml", job=CondorDagNodeInstance)
    '''
    def __init__(self, ifo, description, segment, file_url=None, extension=None, directory=None, **kwargs):       
        self.node=None
        self.ifo = ifo
        self.description = description
        self.segment = segment
        self.kwargs = kwargs  
      
        if not file_url:
            if not extension:
                raise TypeError("a file extension required if a file_url "
                                "is not provided")
            if not directory:
                raise TypeError("a directory is required if a file_url is "
                                "not provided")
                                        
            filename = self._filename(ifo, description, extension, segment)
            path = os.path.join(directory, filename)
            file_url = urlparse.urlunparse(['file', 'localhost', path, None, None, None])
       
        if not isinstance(file_url, list):
            file_url = [file_url]
       
        self.cache_entries = []
        for url in file_url:
            cache_entry = lal.CacheEntry(ifo, description, segment, url)
            self.cache_entries.append(cache_entry)

    @property
    def paths(self):
        return [cache.path for cache in self.cache_entries]
    
    @property
    def filenames(self):
        return [basename(path) for path in self.paths]
       
    @property
    def path(self):
        if len(self.paths) != 1:
            raise TypeError('A single path cannot be returned. This AhopeFile '
                            'is partitioned into multiple physical files.')
        return self.paths[0]
    
    def partition_self(self, num_parts):
        new_entries = []
        path_group = []
        job_tags = []
        for num in range(0, num_parts):
            paths = []
            tag = str(num)
            for entry in self.cache_entries:
                fol, base = os.path.split(entry.path)
                ifo, descr, time, duration = base.split('-')
                path = '%s-%s_%s-%s-%s' % (ifo, descr, tag, time, duration) 
                path = os.path.join(fol, path)                          
                new_entry = lal.CacheEntry(self.ifo, self.description, 
                                           self.segment, entry.url)
                new_entry.path = path                                            
                paths.append(path)
                new_entries.append(new_entry)
            path_group.append(paths)
            job_tags.append(tag)
        self.cache_entries = new_entries
        return path_group, job_tags
        
    @property
    def filename(self):
        if len(self.paths) != 1:
            raise TypeError('A single filename cannot be returned. This '
                            'file is partitioned into multiple physical files.')
        return self.filenames[0]
        
    def _filename(self, ifo, description, extension, segment):
        """ Construct the standard output filename
        """        
        if extension.startswith('.'):
            extension = extension[1:]
        duration = str(int(segment[1] - segment[0]))
        start = str(segment[0])
        
        return "%s-%s-%s-%s.%s" % (ifo, description.upper(), start, duration, extension)     
    
class AhopeFileList(list):
    '''This class holds a list of AhopeOutFile objects. It inherits from the
    built-in list class, but also allows a number of features. ONLY
    AhopeOutFile instances should be within a AhopeOutFileList instance.
    '''
    entry_class = AhopeFile

    def find_output(self, ifo, time):
        '''
        Return AhopeOutFile that covers the given time, or is most
        appropriate for the supplied time range.

        Parameters
        -----------
        ifo : string
           Name of the ifo that the 
        time : int/float/LIGOGPStime or tuple containing two values
           If int/float/LIGOGPStime (or similar may of specifying one time) is
           given, return the AhopeOutFile corresponding to the time. This calls
           self.find_output_at_time(ifo,time).
           If a tuple of two values is given, return the AhopeOutFile that is
           **most appropriate** for the time range given. This calls
           self.find_output_in_range

        Returns
        --------
        AhopeOutFile class
           The AhopeOutFile that corresponds to the time/time range
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
       '''Return AhopeOutFile that covers the given time.

        Parameters
        -----------
        ifo : string
           Name of the ifo that the AhopeOutFile should correspond to
        time : int/float/LIGOGPStime
           Return the AhopeOutFiles that covers the supplied time. If no
           AhopeOutFile covers the time this will return None.

        Returns
        --------
        list of AhopeOutFile classes
           The AhopeOutFiles that corresponds to the time.
        '''
       # Get list of AhopeOutFiles that overlap time, for given ifo
       outFiles = [i for i in self if ifo == i.ifo and time in i.segment] 
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

    def find_output_in_range(self,ifo,start,end):
        '''Return the AhopeOutFile that is most appropriate for the supplied
        time range. That is, the AhopeOutFile whose coverage time has the
        largest overlap with the supplied time range. If no AhopeOutFiles
        overlap the supplied time window, will return None.

        Parameters
        -----------
        ifo : string
           Name of the ifo that the AhopeOutFile should correspond to
        start : int/float/LIGOGPStime 
           The start of the time range of interest.
        end : int/float/LIGOGPStime
           The end of the time range of interest

        Returns
        --------
        AhopeOutFile class
           The AhopeOutFile that is most appropriate for the time range
        '''
        # First filter AhopeOutFiles corresponding to ifo
        outFiles = [i for i in self if ifo == i.ifo] 
        if len(outFiles) == 0:
            # No AhopeOutFiles correspond to that ifo
            return None
        # Filter AhopeOutFiles to those overlapping the given window
        currSeg = segments.segment([start,end])
        outFiles = [i for i in outFiles if i.segment.intersects(currSeg)]
        
        if len(outFiles) == 0:
            # No AhopeOutFile overlap that time period
            return None
        elif len(outFiles) == 1:
            # One AhopeOutFile overlaps that period
            return outFiles[0]
        else:
            # More than one AhopeOutFile overlaps period. Find lengths of
            # overlap between time window and AhopeOutFile window
            overlapWindows = [abs(i.segment & currSeg) for i in outFiles]           
            # Return the AhopeOutFile with the biggest overlap
            # Note if two AhopeOutFile have identical overlap, this will return
            # the first AhopeOutFile in the list
            overlapWindows = numpy.array(overlapWindows,dtype = int)
            return outFiles[overlapWindows.argmax()]

    def find_all_output_in_range(self, ifo, currSeg):
        """
        Return all files that overlap the specified segment.
        """
        outFiles = [i for i in self if ifo == i.ifo]
        outFiles = [i for i in outFiles if i.segment.intersects(currSeg)]
        return self.__class__(outFiles)


class AhopeOutSegFile(AhopeFile):
    '''
    This class inherits from the AhopeOutFile class, and is designed to store
    ahope output files containing a segment list. This is identical in
    usage to AhopeOutFile except for an additional kwarg for holding the
    segment list, if it is known at ahope run time.
    '''
    def __init__(self, ifo, description, timeSeg, fileUrl,
                 segList=None, **kwargs):
        """
        ADD DOCUMENTATION
        """
        AhopeFile.__init__(self, ifo, description, timeSeg, fileUrl,
                              **kwargs)
        self.segmentList = segList

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
        newSegList = segments.segmentlist()
        for seg in self.segmentList:
            if abs(seg) > minSegLength:
                newSegList.append(seg)
        newSegList.coalesce()
        self.segmentList = newSegList
        self.toSegmentXml()

    def toSegmentXml(self):
        """
        Write the segment list in self.segmentList to the url in self.url.
        """
        filePointer = open(self.path, 'w')
        dqUtils.tosegmentxml(filePointer, self.segmentList)
        filePointer.close()

def make_external_call(cmdList, outDir=None, outBaseName='external_call',
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
    outDir : string
        If given the stdout and stderr will be redirected to
        os.path.join(outDir,outBaseName+[".err",".out])
        If not given the stdout and stderr will not be recorded
    outBaseName : string
        The value of outBaseName used to construct the file names used to
        store stderr and stdout. See outDir for more information.
    shell : boolean, default=False
        This value will be given as the shell kwarg to the subprocess call.
        **WARNING** See the subprocess documentation for details on this
        Kwarg including a warning about a serious security exploit. Do not
        use this unless you are sure it is necessary **and** safe.
    fail_on_error : boolean, default=True
        If set to true an exception will be raised if the external command does
        not return a code of 0. If set to false such failures will be ignored.
        Stderr and Stdout can be stored in either case using the outDir
        and outBaseName options.

    Returns
    --------
    exitCode : int
        The code returned by the process.
    """
    if outDir:
        outBase = os.path.join(outDir,outBaseName)
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
    and checking has been requested
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
            msg += "Stderr can be found in %s.\n" %(self.errFile)
        if self.outFile:
            msg += "Stdout can be found in %s.\n" %(self.outFile)
        if self.cmdFile:
            msg += "The failed command has been printed in %s." %(self.cmdFile)
        return msg
              

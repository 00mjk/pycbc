from __future__ import division

from glue import pipeline
from glue import segments

def select_tmpltbank_instance(tmpltBankExe):
    """This function returns an instance of the class that is appropriate for
    the given executable provided to the function.
    
    Parameters
    ----------
    tmpltbankExe : string
        The name of the executable that is being used.

    Returns
    --------
    Instanced class : exeClass
        An instance of the class that holds the utility functions appropriate
        for the given executable. This class **must** contain
        * exeClass.get_tmpltbank_valid_times()
        * exeClass.add_tmpltbank_job()
        * exeClass.add_tmpltbank_node()
        See lalapps_tmpltbank_utils for an example of how to set this up.
    """

    # This is basically a list of if statements
    if tmpltBankExe == 'lalapps_tmpltbank':
        exeClass = lalapps_tmpltbank_utils
    # Some elif statements
    else:
        # Should we try some sort of default class??
        errString = "No class exists for executable %s" %(tmpltBankExe,)
        raise NotImplementedError(errString)

    return exeClass()
   
class default_utils:
    """
    STUB: This is the start of code to try to run using default settings.
    """
    def get_tmpltbank_valid_times(self,cp,ifo):
        """
        Return the length of data that the tmpltbank job will need to read and
        the part of that data that the template bank is valid for.

        Parameters
        ----------
        cp : ConfigParser object
            The ConfigParser object holding the ahope configuration settings
        ifo : string
            The interferometer being setup. It is possible to use different
            configuration settings for each ifo.

        Returns
        -------
        dataLength : float (seconds)
            The length of data that the job will need
        validChunk : glue.glue.segments.segment
            The start and end of the dataLength that is valid for the template
            bank.
        """
        # Take default option from .ini file
        dataDuration = cp.get('ahope','tmpltbank-data-duration')
        validStart = cp.get('ahope','tmpltbank-valid-start')
        validEnd = cp.get('ahope','tmpltbank-valid-end')
        validChunk = segments.segment([validStart,validEnd])

        return dataDuration,validChunk

class lalapps_tmpltbank_utils:
    """This class holds all the utility functions to set up lalapps_tmpltbank
    jobs.
    """

    def get_tmpltbank_valid_times(self,cp,ifo):
        """
        Return the length of data that the tmpltbank job will need to read and
        the part of that data that the template bank is valid for. In the case
        of lalapps_tmpltbank the following options are needed to set this up
        and will be used by the executable to figure this out:
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

        Parameters
        ----------
        cp : ConfigParser object
            The ConfigParser object holding the ahope configuration settings
        ifo : string
            The interferometer being setup. It is possible to use different
            configuration settings for each ifo.

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
        padData = int(cp.get_opt_ifo('tmpltbank','pad-data',ifo))
        segmentLength = float(cp.get_opt_ifo('tmpltbank',\
                                             'segment-length',ifo))
        sampleRate = float(cp.get_opt_ifo('tmpltbank','sample-rate',ifo))
        numSegments = int(cp.get_opt_ifo('tmpltbank','number-of-segments',ifo))
        # Calculate total valid duration
        analysisDur = int(segmentLength/sampleRate) * (numSegments + 1)/2
        if (segmentLength % sampleRate):
            errString = "In tmpltbank, when running lalapps_tmpltbank "
            errString += "segment-length must be a multipl of sample-rate."
            raise ValueError(errString)
        # Set the segments
        dataLength = analysisDur + 2*padData
        validStart = padData
        validEnd = analysisDur + padData
        validChunk = segments.segment([validStart,validEnd])

        return dataLength,validChunk

    def create_tmpltbank_condorjob(self,cp,ifo):
        '''
        Set up a CondorDagmanJob class appropriate for lalapps_tmpltbank.

        Parameters
        ----------
        cp : ConfigParser object
            The ConfigParser object holding the ahope configuration settings
        ifo : string
            The interferometer being setup. It is possible to use different
            configuration settings for each ifo.

        Returns
        -------
        pipeline.CondorDagmanJob
            The lalapps_tmpltbank CondorDagmanJob class.
        '''
        sections = ['tmpltbank']
        if cp.has_section('tmpltbank-%s' %(ifo.lower())):
             sections.append('tmpltbank-%s' %(ifo.lower()) )
    
        tmpltBankJob = LegacyInspiralAnalysisJob(cp,sections,\
                                             'tmpltbank','standard')
        tmpltBankJob.ifo = ifo

        return tmpltBankJob

    def create_tmpltbank_condornode(self,ahopeDax,tmpltBankJob,bankDataSeg):
        """
        Set up a CondorDagmanNode class to run a lalapps_tmpltbank instance.

        Parameters
        ----------
        ahopeDax : pipeline.CondorDAG instance
            The workflow to hold of the ahope jobs
        tmpltBankJob : pipeline.CondorDagmanJob
            The CondorDagmanJob to use when setting up the individual nodes
        bankDataSeg : glue.segments.segment
            Segment holding the data that needs to be used for this node

        Returns
        --------
        tmpltBankNode : pipeline.CondorDagmanNode
            The node to run the job
        string
            The output file
        """
        tmpltBankNode = LegacyInspiralAnalysisNode(tmpltBankJob)
        tmpltBankNode.set_category('tmpltbank')
        # Does this need setting?: tmpltBankNode.set_priority(?)
        tmpltBankNode.set_start(bankDataSeg[0])
        tmpltBankNode.set_end(bankDataSeg[1])
        tmpltBankNode.set_ifo(tmpltBankJob.ifo)
        tmpltBankNode.finalize()
        ahopeDax.add_node(tmpltBankNode)

        return tmpltBankNode,tmpltBankNode.get_output()
    

class LegacyInspiralAnalysisJob(pipeline.AnalysisJob, pipeline.CondorDAGJob):
    """
    This class inherits from the CondorDAGJob class and adds methods that are
    used for C-codes that used to run in ihope. The LegacyInspiralAnalysisJob
    captures some of the common features of the specific inspiral jobs that
    appear below.  Specifically, the universe and exec_name are set, the stdout
    and stderr from the job are directed to the logs directory. The path to the
    executable is determined from the ini file.
    """

    def __init__(self,cp,sections,exec_name,universe,extension='xml'):
        """
        Initialize the LegacyInspiralAnalysisJob class.
   
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
        self.__exec_name = exec_name
        self.__extension = extension
        executable = cp.get('executables',exec_name)
        pipeline.CondorDAGJob.__init__(self,universe,executable)
        pipeline.AnalysisJob.__init__(self,cp,dax=True)
        self.add_condor_cmd('copy_to_spool','False')

        for sec in sections:
            if cp.has_section(sec):
                self.add_ini_opts(cp, sec)
            else:
                warnString = "warning: config file is missing section [%s]"\
                             %(sec,)
                print >>sys.stderr, warnString

        logBaseNam = 'logs/%s-$(macrogpsstarttime)' %(exec_name,)
        logBaseNam += '-$(macrogpsendtime)-$(cluster)-$(process)'

        self.set_stdout_file('%s.out' %(logBaseNam,) )
        self.set_stderr_file('%s.err' %(logBaseNam,) )
        self.set_sub_file('%s.sub' %(exec_name,) )

    def set_exec_name(self,exec_name):
        """
        Set the exec_name name 
        """
        self.__exec_name = exec_name

    def get_exec_name(self):
        """
        Get the exec_name name
        """
        return self.__exec_name

    def set_extension(self,extension):
        """
        Set the file extension
        """
        self.__extension = extension

    def get_extension(self):
        """
        Get the extension for the file name
        """
        return self.__extension

class LegacyInspiralAnalysisNode(pipeline.AnalysisNode,\
                                 pipeline.CondorDAGNode):
    """
    A LegacyInspiralAnalysisNode instance runs an example of legacy ihope code
    in a Condor DAX.
    """
    def __init__(self,job):
        """
        Initialize the LegacyInspiralAnalysisNode.
    
        Parameters
        -----------
        job : pipeline.CondorDAGJob
            A CondorDAGJob that can run an instance of the particular
            executable.
        """
        pipeline.CondorDAGNode.__init__(self,job)
        pipeline.AnalysisNode.__init__(self)
        opts = job.get_opts()
    
        if ("pad-data" in opts) and int(opts['pad-data']):
            self.set_pad_data(int(opts['pad-data']))

        self.__zip_output = ("write-compress" in opts)

    def set_zip_output(self,zip):
        """
        Set the zip output flag
        """
        self.__zip_output = zip
 
    def get_zip_output(self):
        """
        Set the zip output flag
        """
        return self.__zip_output

    def get_output_base(self):
        """
        Returns the base file name of output from the inspiral code. This is 
        assumed to follow the standard naming convention:

        IFO-EXECUTABLE_IFOTAG_USERTAG-GPS_START-DURATION
        """
        if not self.get_start() or not self.get_end() or not self.get_ifo():
            raise ValueError, "Start time, end time or ifo has not been set"

        filebase = self.get_ifo() + '-' + self.job().get_exec_name().upper()

        if self.get_ifo_tag():
            filebase += '_' + self.get_ifo_tag()
        if self.get_user_tag():
            filebase += '_' + self.get_user_tag()

        filebase +=  '-' + str(self.get_start()) + '-' + \
                     str(self.get_end() - self.get_start())

        return(filebase)

    def get_output(self):
        """
        Returns the file name of output from the inspiral code. This is
        obtained from the get_output_base() method, with the correct extension
        added.
        """
        filename = self.get_output_base()
        filename += '.' + self.job().get_extension()

        if self.get_zip_output():
            filename += '.gz'

        self.add_output_file(filename)

        return filename

    def finalize(self):
        """
        set the data_start_time and data_end_time
        """
        if self.get_pad_data():
            self.set_data_start(self.get_start() - \
                                self.get_pad_data())
            self.set_data_end(self.get_end() + \
                              self.get_pad_data())

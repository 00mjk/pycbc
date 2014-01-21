import math
from glue import segments
from pycbc.ahope.ahope_utils import *
from pycbc.ahope.legacy_ihope import *

def select_tmpltbankjob_instance(curr_exe, curr_section):
    """This function returns an instance of the class that is appropriate for
    creating a template bank within ihope.
    
    Parameters
    ----------
    curr_exe : string
        The name of the executable that is being used.
    curr_section : string
        The name of the section storing options for this executble

    Returns
    --------
    Instanced class : exe_class
        An instance of the class that holds the utility functions appropriate
        for the given executable. This class **must** contain
        * exe_class.get_valid_times(ifo, )
        * exe_class.create_job()
        * exe_class.create_node()
    """
    # This is basically a list of if statements

    if curr_exe == 'lalapps_tmpltbank':
        exe_class = LegacyTmpltbankExec(curr_section)
    elif curr_exe == 'pycbc_geom_nonspinbank':
        exe_class = PyCBCTmpltbankExec(curr_section)
    else:
        # Should we try some sort of default class??
        err_string = "No class exists for executable %s" %(curr_exe,)
        raise NotImplementedError(err_string)
    return exe_class

def select_matchedfilterjob_instance(curr_exe, curr_section):
    """This function returns an instance of the class that is appropriate for
    matched-filtering within ahope.
    
    Parameters
    ----------
    curr_exe : string
        The name of the executable that is being used.
    curr_section : string
        The name of the section storing options for this executble

    Returns
    --------
    Instanced class : exe_class
        An instance of the class that holds the utility functions appropriate
        for the given executable. This class **must** contain
        * exe_class.get_valid_times()
        * exe_class.create_condorjob()
        * exe_class.create_condornode()
    """
    # This is basically a list of if statements
    if curr_exe == 'lalapps_inspiral':
        exe_class = LegacyInspiralExec(curr_section)
    elif curr_exe == 'pycbc_inspiral':
        exe_class = PyCBCInspiralExec(curr_section)
    else:
        # Should we try some sort of default class??
        err_string = "No class exists for executable %s" %(curr_exe,)
        raise NotImplementedError(err_string)
        
    return exe_class

def select_splitfilejob_instance(curr_exe, curr_section):
    """This function returns an instance of the class that is appropriate for
    splitting an output file up within ahope (for e.g. splitbank).
    
    Parameters
    ----------
    curr_exe : string
        The name of the executable that is being used.
    curr_section : string
        The name of the section storing options for this executble

    Returns
    --------
    Instanced class : exe_class
        An instance of the class that holds the utility functions appropriate
        for the given executable. This class **must** contain
        * exe_class.create_job()
        * exe_class.create_node()
    """
    # This is basically a list of if statements
    if curr_exe == 'lalapps_splitbank':
        exe_class = LegacySplitBankExec(curr_section)
    # Some elif statements
    else:
        # Should we try some sort of default class??
        err_string = "No class exists for executable %s" %(curr_exe,)
        raise NotImplementedError(errString)

    return exe_class

def sngl_ifo_job_setup(workflow, ifo, out_files, exe_instance, science_segs, 
                       datafind_outs, output_dir, parents=None, 
                       link_exe_instance=False, allow_overlap=True):
    """
    This function sets up a set of single ifo jobs.

    Parameters
    -----------
    workflow: Workflow
        An instanced class that manages the constructed workflow.
    ifo : string
        The name of the ifo to set up the jobs for
    out_files : AhopeOutFileList or AhopeOutGroupList
        The AhopeOutFileList containing the list of jobs. Jobs will be appended
        to this list, and it does not need to be empty when supplied.
    exe_instance : Instanced class
        An instanced class that contains the functions needed to set up things
        that are specific to the executable being run.
    science_segs : segments.segmentlist
        The list of times that the jobs should cover
    datafind_outs : AhopeFileList
        The file list containing the datafind files.
    output_dir : path string
        The directory where data products will be placed.
    parents : AhopeFileList (optional, kwarg, default=None)
        The AhopeOutFileList containing the list of jobs that are parents to
        the one being set up.
    link_exe_instance : Executable instance (optional),
        Coordinate the valid times with another executable.
    allow_overlap : boolean (optional, kwarg, default = True)
        If this is set the times that jobs are valid for will be allowed to
        overlap. This may be desired for template banks which may have some
        overlap in the times they cover. This may not be desired for inspiral
        jobs, where you probably want triggers recorded by jobs to not overlap
        at all.
    """
    cp = workflow.cp
    
    # Begin by getting analysis start and end, and start and end of time
    # that the output file is valid for
    data_length, valid_chunk = exe_instance.get_valid_times(cp, ifo)
    valid_length = abs(valid_chunk)

    data_chunk = segments.segment([0, data_length])
    job_tag = exe_instance.exe_name.upper()
    
    if link_exe_instance:
        # EURGHH! What we are trying to do here is, if this option is given,
        # line up the template bank and inspiral jobs so that there is one
        # template bank for each inspiral job. This is proving a little messy
        # and probably still isn't perfect.

        # What data does the linked exe use?
        link_data_length, link_valid_chunk = \
                             link_exe_instance.get_valid_times(cp, ifo)
        # What data is lost at start and end from either job?
        start_data_loss = max(valid_chunk[0], link_valid_chunk[0])
        end_data_loss = max(data_length - valid_chunk[1],\
                            link_data_length - link_valid_chunk[1])
        # Correct the data for both jobs
        valid_chunk = segments.segment(start_data_loss, \
                                       data_length - end_data_loss)
        link_valid_chunk = segments.segment(start_data_loss, \
                                       link_data_length - end_data_loss)
        valid_length = abs(valid_chunk)
        link_valid_length = abs(link_valid_chunk)

        # Which one is now longer? Use this is valid_length
        if link_valid_length < valid_length:
            valid_length = link_valid_length

    # DO NOT! use valid length here, as valid_length and abs(valid_chunk)
    # may be different by this point if using link_exe_instance
    data_loss = data_length - abs(valid_chunk)


    # Set up the condorJob class for the current executable
    curr_exe_job = exe_instance.create_job(cp, ifo, output_dir)
    
    if data_loss < 0:
        raise ValueError("Ahope needs fixing! Please contact a developer")
        
    # Loop over science segments and set up jobs
    for curr_seg in science_segs:
        # Is there enough data to analyse?
        curr_seg_length = abs(curr_seg)
        if curr_seg_length < data_length:
            continue
        # How many jobs do we need
        curr_seg_length = float(abs(curr_seg))
        num_jobs = int( math.ceil( \
                 (curr_seg_length - data_loss) / float(valid_length) ))
        # What is the incremental shift between jobs
        time_shift = (curr_seg_length - data_length) / float(num_jobs - 1)
        for job_num in range(num_jobs):
            # Get the science segment for this job
            shift_dur = curr_seg[0] + int(time_shift * job_num)
            job_data_seg = data_chunk.shift(shift_dur)
            job_valid_seg = valid_chunk.shift(shift_dur)
            # If we need to recalculate the valid times to avoid overlap
            if not allow_overlap:
                data_per_job = (curr_seg_length - data_loss) / float(num_jobs)
                lower_boundary = job_num*data_per_job + \
                                     valid_chunk[0] + curr_seg[0]
                upper_boundary = data_per_job + lower_boundary
                # NOTE: Convert to int after calculating both boundaries
                # small factor of 0.0001 to avoid float round offs causing us to
                # miss a second at end of segments.
                lower_boundary = int(lower_boundary)
                upper_boundary = int(upper_boundary + 0.0001)
                if lower_boundary < job_valid_seg[0] or \
                        upper_boundary > job_valid_seg[1]:
                    err_msg = ("Ahope is attempting to generate output "
                              "from a job at times where it is not valid.")
                    raise ValueError(err_msg)
                job_valid_seg = segments.segment([lower_boundary, 
                                                  upper_boundary])
                
            if parents:
                curr_parent = parents.find_output(ifo, job_valid_seg)
                if not curr_parent:
                    err_string = ("No parent jobs found overlapping %d to %d." 
                                  %(job_valid_seg[0], job_valid_seg[1]))
                    err_string += "\nThis is a bad error! Contact a developer."
                    raise ValueError(err_string)
            else:
                curr_parent = None

            if datafind_outs:
                curr_dfouts = datafind_outs.find_all_output_in_range(ifo, 
                                                                  job_data_seg)
                if not curr_dfouts:
                    err_str = ("No datafind jobs found overlapping %d to %d."
                                %(job_data_seg[0],job_data_seg[1]))
                    err_str += "\nThis shouldn't happen. Contact a developer."
                    raise ValueError(err_str)

            node = curr_exe_job.create_node(job_data_seg, job_valid_seg, 
                                            parent=curr_parent,
                                            dfParents=curr_dfouts)
            workflow.add_node(node)
            out_files += node.output_files
    return out_files

class PyCBCInspiralJob(Job):
    def __init__(self, cp, exe_name, universe, ifo=None, out_dir=None):
        Job.__init__(self, cp, exe_name, universe, ifo, out_dir)
        self.set_memory(2000)
        if self.get_opt('processing-scheme') == 'cuda':
            self.needs_gpu()

    def create_node(self, data_seg, valid_seg, parent=None, dfParents=None):
        node = LegacyAnalysisNode(self)

        pad_data = int(self.get_opt('pad-data'))
        if pad_data is None:
            raise ValueError("The option pad-data is a required option of "
                             "%s. Please check the ini file." % self.exe_name)

        if not dfParents or len(dfParents) != 1:
            raise ValueError("%s must be supplied with a single cache file"
                              %(self.exe_name))

        # set remaining options flags   
        node.set_start(data_seg[0] + pad_data)
        node.set_end(data_seg[1] - pad_data)
        node.set_trig_start(valid_seg[0])
        node.set_trig_end(valid_seg[1])

        cache_file = dfParents[0]

        # FIXME add control for output type         
        insp = AhopeFile(self.ifo, self.exe_name, extension='.xml.gz',
                         segment=valid_seg,
                         directory=self.out_dir)

        # set the input and output files        
        node.add_output(insp, opts='output')
        node.add_input(cache_file, opts='frame-cache')
        node.add_input(parent, opts='bank-file')
        return node

class PyCBCInspiralExec(Executable):
    def create_job(self, cp, ifo, out_dir=None):
        return PyCBCInspiralJob(cp, self.exe_name, self.condor_universe,
                                ifo=ifo, out_dir=out_dir)

    def get_valid_times(self, cp, ifo):
        pad_data = int(cp.get_opt_ifo(self.exe_name, 'pad-data', ifo))
        start_pad = int(cp.get_opt_ifo(self.exe_name, 'segment-start-pad', ifo))
        end_pad = int(cp.get_opt_ifo(self.exe_name, 'segment-end-pad', ifo))

        #FIXME this should not be hard coded (can be any integer > 
        #segment_length with pycbc_inspiral)
        data_length = 2560 + pad_data * 2
        start = pad_data + start_pad
        end = data_length - pad_data - end_pad
        return data_length, segments.segment(start, end)

class PyCBCTmpltbankJob(Job):
    def __init__(self, cp, exe_name, universe, ifo=None, out_dir=None):
        Job.__init__(self, cp, exe_name, universe, ifo, out_dir)
        self.set_memory(2000)

    def create_node(self, data_seg, valid_seg, parent=None, dfParents=None):
        node = LegacyAnalysisNode(self)

        if not dfParents or len(dfParents) != 1:
            raise ValueError("%s must be supplied with a single cache file"
                              %(self.exe_name))

        pad_data = int(self.get_opt('pad-data'))
        if pad_data is None:
            raise ValueError("The option pad-data is a required option of "
                             "%s. Please check the ini file." % self.exe_name)

        # set the remaining option flags
        node.set_start(data_seg[0] + pad_data)
        node.set_end(data_seg[1] - pad_data)

        cache_file = dfParents[0]

        # FIXME add control for output type                       
        insp = AhopeFile(self.ifo, self.exe_name, extension='.xml.gz',
                         segment=valid_seg,
                         directory=self.out_dir)

        # set the input and output files      
        node.add_output(insp, opts='output-file')
        node.add_input(cache_file, opts='frame-cache')
        return node

class PyCBCTmpltbankExec(Executable):
    def create_job(self, cp, ifo, out_dir=None):
        return PyCBCTmpltbankJob(cp, self.exe_name, self.condor_universe,
                                 ifo=ifo, out_dir=out_dir)

    def get_valid_times(self, cp, ifo):
        pad_data = int(cp.get_opt_ifo(self.exe_name, 'pad-data', ifo))

        #FIXME this should not be hard coded 
        data_length = 2560 + pad_data * 2
        start = pad_data
        end = data_length - pad_data
        return data_length, segments.segment(start, end)

class LigolwAddJob(Job):
    def __init__(self, cp, exe_name, universe, ifo=None, out_dir=None):
        Job.__init__(self, cp, exe_name, universe, ifo, out_dir)
        self.set_memory(2000)

    def create_node(self, FIXME_INPUTS):
        # NOT WRITTEN YET!
        pass

class LigolwAddExec(Executable):
    def __init__(self, exe_name):
        Executable.__init__(self, exe_name, 'vanilla')

    def create_job(self, cp, ifo, out_dir=None):
        return LigolwAddJob(cp, self.exe_name, self.condor_universe,
                            ifo=ifo, out_dir=out_dir)

class LigolwThincaJob(Job):
    def __init__(self, cp, exe_name, universe, ifo=None, out_dir=None):
        Job.__init__(self, cp, exe_name, universe, ifo, out_dir)
        self.set_memory(2000)

    def create_node(self, FIXME_INPUTS):
        # NOT WRITTEN YET!
        pass

class LigolwThincaExec(Executable):
    def __init__(self, exe_name):
        Executable.__init__(self, exe_name, 'vanilla')

    def create_job(self, cp, ifo, out_dir=None):
        return LigolwThincaJob(cp, self.exe_name, self.condor_universe,
                            ifo=ifo, out_dir=out_dir)


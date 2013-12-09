import os,sys,optparse
import urlparse,urllib
import logging
from glue import datafind
from glue import segments,segmentsUtils,git_version
from pycbc.ahope import AhopeOutGroupList, AhopeOutFileList, AhopeOutGroup

def setup_datafind_workflow(cp, scienceSegs, ahopeDax, outputDir, \
                            checkFramesExist=True, checkSegmentGaps=True, \
                            updateSegmentTimes=False):
    """
    Setup datafind section of ahope workflow. This section is responsible for
    generating, or setting up the workflow to generate, a list of files that
    record the location of the frame files needed to perform the analysis.
    There could be multiple options here, the datafind jobs could be done at
    run time or could be put into a dag. The subsequent jobs will know
    what was done here from the AhopeOutFileList containing the datafind jobs
    (and the Dagman nodes if appropriate.
    For now the only implemented option is to generate the datafind files at
    runtime. This module can also check if the frameFiles actually exist, check
    whether the obtained segments line up with the original ones and update the
    science segments to reflect missing data files.

    Parameters
    ----------
    cp : ConfigParser.ConfigParser instance
        This contains a representation of the information stored within the
        ahope configuration files
    scienceSegs : Dictionary of ifo keyed glue.segment.segmentlist instances
        This contains the times that ahope is expected to analyse.
    ahopeDax : glue.pipeline.CondorDagman instance
        This stores the worklow to be run under condor. Currently this is not
        used within this module, but is here to allow the possibility to run
        datafind jobs under condor in ahope.
    outputDir : path
        All output files written by datafind processes will be written to this
        directory.
    checkFramesExist : boolean (optional, default=True)
        If this option is given ahope will check if all of the returned frame
        files are accessible from the machine that is running ahope. It will
        raise a ValueError if frames cannot be found.
    checkSegmentGaps : boolean (optional, default=True)
        If this option is given ahope will check that the local datafind server
        has returned frames covering all of the listed science times. It will
        raise a ValueError if there are gaps.
    updateSegmentTimes : boolean (optional, default=True)
        If this option is given ahope will check that the local datafind server
        has returned frames covering all of the listed science times. If there
        are gaps ahope will remove these times from the scienceSegs lists.

    Returns
    --------
    datafindOuts : AhopeOutGroupList
        List of all the datafind output files for use later in the pipeline.
    scienceSegs : Dictionary of ifo keyed glue.segment.segmentlist instances
        This contains the times that ahope is expected to analyse. If the 
        updateSegmentTimes kwarg is given this will be updated to reflect any
        instances of missing data.
    """
    logging.info("Entering datafind module")

    logging.info("Starting datafind with setup_datafind_runtime_generated")
    datafindOuts = setup_datafind_runtime_generated(cp, scienceSegs, outputDir)
    logging.info("setup_datafind_runtime_generated completed")
    # If we don't have frame files covering all times we can update the science
    # segments.
    if updateSegmentTimes or checkSegmentGaps:
        logging.info("Checking science segments against datafind output....")
        newScienceSegs = get_science_segs_from_datafind_outs(datafindOuts)
        logging.info("Datafind segments calculated.....")
        missingData = False
        for ifo in scienceSegs.keys():
            # If no data in the input then do nothing
            if not scienceSegs[ifo]:
                msg = "No input science segments for ifo %s " %(ifo)
                msg += "so, surprisingly, no data has been found. "
                msg += "Was this expected?"
                logging.warning(msg)
                continue
            if not newScienceSegs.has_key(ifo):
                msg = "IFO %s's science segments " %(ifo)
                msg += "are completely missing."
                logging.error(msg)
                missingData = True
                continue
            missing = scienceSegs[ifo] - newScienceSegs[ifo]
            if abs(missing):
                msg = "From ifo %s we are missing segments:" %(ifo)
                msg += "\n%s" % "\n".join(map(str, missing))
                missingData = True
                logging.error(msg)
            # Remove missing time, so that we can carry on if desired
            scienceSegs[ifo] = scienceSegs[ifo] - missing
        if checkSegmentGaps and missingData:
            raise ValueError("Ahope cannot find needed data, exiting.")
        logging.info("Done checking, any discrepancies are reported above.")

    # Do all of the frame files that were returned actually exist?
    if checkFramesExist:
        logging.info("Verifying that all frames exist on disk.")
        missingFlag = False
        for dfGroup in datafindOuts:
            _,missingFrames = dfGroup.get_output().checkfilesexist(\
                                                     on_missing="warn")
            if missingFrames:
                missingFlag = True
                logging.error("Files missing from cache %s." \
                              %(dfGroup.summaryUrl))
                msg = "Full file of files inaccessible from this cache:\n"
                msg +='\n'.join([a.url for a in missingFrames])
                logging.error(msg)
        if missingFlag:
            raise ValueError("Some frames cannot be found on disk.")
        logging.info("All frames found successfully")

    logging.info("Leaving datafind module")
    return datafindOuts, scienceSegs
    

def setup_datafind_runtime_generated(cp, scienceSegs, outputDir):
    """
    This function uses the glue.datafind library to obtain the location of all
    the frame files that will be needed to cover the analysis of the data
    given in scienceSegs. This function will not check if the returned frames
    cover the whole time requested, such sanity checks are done in the
    pycbc.ahope.setup_datafind_workflow entry function.

    Parameters
    -----------
    cp : ConfigParser.ConfigParser instance
        This contains a representation of the information stored within the
        ahope configuration files
    scienceSegs : Dictionary of ifo keyed glue.segment.segmentlist instances
        This contains the times that ahope is expected to analyse.
    outputDir : path
        All output files written by datafind processes will be written to this
        directory.

    Returns
    --------
    datafindOuts : AhopeOutGroupList
        List of all the datafind output files for use later in the pipeline.

    """
    # First job is to do setup for the datafind jobs
    # First get the server name
    logging.info("Setting up connection to datafind server.")
    if cp.has_option("ahope-datafind", "datafind-ligo-datafind-server"):
        datafindServer = cp.get("ahope-datafind",\
                                "datafind-ligo-datafind-server")
    else:
        # Get the server name from the environment
        if os.environ.has_key("LIGO_DATAFIND_SERVER"):
            datafindServer = os.environ["LIGO_DATAFIND_SERVER"]
        else:
            errMsg = "Trying to obtain the ligo datafind server url from "
            errMsg += "the environment, ${LIGO_DATAFIND_SERVER}, but that "
            errMsg += "variable is not populated."
            raise ValueError(errMsg)

    # verify authentication options
    if not datafindServer.endswith("80"):
        cert_file, key_file = datafind.find_credential()
    else:
        cert_file, key_file = None, None

    # Is a port specified in the server URL
    server, port = datafindServer.split(':',1)
    if port == "":
        port = None
    else:
        port = int(port)

    # Open connection to the datafind server
    if cert_file and key_file:
        #HTTPS connection
        connection =\
            datafind.GWDataFindHTTPSConnection(host=server, port=port, \
                                   cert_file=cert_file, key_file=key_file)
    else:
        # HTTP connection
        connection =\
            datafind.GWDataFindHTTPConnection(host=server, port=port)

    # Now ready to loop over the input segments
    datafindOuts = AhopeOutGroupList([])
    ifos = scienceSegs.keys()
    jobTag = "DATAFIND"
    logging.info("Querying datafind server for all science segments.")
    for ifo, scienceSegsIfo in scienceSegs.items():
        observatory = ifo[0].upper()
        frameType = cp.get("ahope-datafind", "datafind-%s-frame-type"%(ifo))
        for seg in scienceSegsIfo:
            msg = "Finding data between %d and %d " %(seg[0],seg[1])
            msg += "for ifo %s" %(ifo)
            logging.debug(msg)
            # WARNING: For now ahope will expect times to be in integer seconds
            startTime = int(seg[0])
            endTime = int(seg[1])
            # Take the datafind KWargs from config (usually urltype=file is
            # given).
            dfKwargs = {}
            for item, value in cp.items("datafind"):
                dfKwargs[item] = value
            # It is useful to print the corresponding command to the logs
            # directory to check if this was expected.
            log_datafind_command(observatory, frameType, startTime, endTime,\
                                 os.path.join(outputDir,'logs'), **dfKwargs)
            logging.debug("Asking datafind server for frames.")
            dfCache = connection.find_frame_urls(observatory, frameType, \
                        startTime, endTime, **dfKwargs)
            logging.debug("Frames returned")
            dfCacheFileName = "%s-%s-%d-%d.lcf" \
                              %(ifo, jobTag, startTime, endTime-startTime)
            dfCachePath = os.path.join(outputDir, dfCacheFileName)
            # Dump output to file
            fP = open(dfCachePath, "w")
            dfCache.tofile(fP)
            fP.close()
            dfCacheUrl = urlparse.urlunparse(['file', 'localhost',\
                                             urllib.pathname2url(dfCachePath),\
                                             None, None, None])
            # Convert to ahope format
            dfCache = AhopeOutFileList(dfCache)
            urlList = [e.url for e in dfCache] 
            jobSegs = [e.segment for e in dfCache]
            dfCacheGroup = AhopeOutGroup(ifo, jobTag, seg, \
                                         summaryUrl=dfCacheUrl)
            dfCacheGroup.set_output(urlList, None, outSegs=jobSegs)
            datafindOuts.append(dfCacheGroup)

    return datafindOuts

def get_science_segs_from_datafind_outs(datafindOuts):
    """
    This function will calculate the science segments that are covered in
    the AhopeOutGroupList containing the frame files returned by various
    calls to the datafind server. This can then be used to check whether this
    list covers what it is expected to cover.

    Parameters
    ----------
    datafindOuts : AhopeOutGroupList
        List of all the datafind output files.

    Returns
    --------
    newScienceSegs : Dictionary of ifo keyed glue.segment.segmentlist instances
        The times covered by the frames found in datafindOuts.
    """
    newScienceSegs = {}
    for group in datafindOuts:
        if group.get_output():
            groupSegs = segments.segmentlist(e.segment for e \
                                             in group.get_output()).coalesce()
        else:
            continue
        if not newScienceSegs.has_key(group.observatory):
            newScienceSegs[group.observatory] = groupSegs
        else:
            newScienceSegs[group.observatory].extend(groupSegs)
            # NOTE: This .coalesce probably isn't needed as the segments should
            # be disjoint. If speed becomes an issue maybe remove it?
            newScienceSegs[group.observatory].coalesce()
    return newScienceSegs
    
def log_datafind_command(observatory, frameType, startTime, endTime, \
                         outputDir, **dfKwargs):
    """
    This command will print an equivalent gw_data_find command to disk that
    can be used to debug why the internal datafind module is not working.
    """
    gw_command = ['gw_data_find', '--observatory', observatory,\
                  '--type', frameType, \
                  '--gps-start-time', str(startTime), \
                  '--gps-end-time', str(endTime)]

    for name, value in dfKwargs.items():
        gw_command.append("--" + name)
        gw_command.append(str(value))
  
    fileName = "%s-%s-%d-%d.lcf" \
               %(observatory, frameType, startTime, endTime-startTime)
    filePath = os.path.join(outputDir, fileName)
    fP = open(filePath, 'w')
    fP.write(' '.join(gw_command))
    fP.close()

import os, copy, shutil
import logging
from glue import pipeline
from glue import segments
import pycbc.ahope as ahope

logging.basicConfig(format='%(asctime)s:%(levelname)s : %(message)s', 
                    level=logging.INFO,datefmt='%I:%M:%S')

workflow = ahope.Workflow(['./test_ahope.ini', 'inj.ini', 'pipedown.ini'])

# Make directories for output
currDir = os.getcwd()
segDir = os.path.join(currDir, "segments")
if not os.path.exists(segDir+'/logs'):
    os.makedirs(segDir+'/logs')
dfDir = os.path.join(currDir,"datafind")
if not os.path.exists(dfDir+'/logs'):
    os.makedirs(dfDir+'/logs')
if not os.path.exists('full_data/logs'):
    os.makedirs('full_data/logs')
if not os.path.exists('time_slide_files/logs'):
    os.makedirs('time_slide_files/logs')

# Set start and end times

# These are Chris' example S6 day of data
start_time = 961585543
end_time = 961588487

log_directory = "/usr1/spxiwh/logs"

# This is S6D chunk 3, an example full-scale ihope analysis time-frame
##start_time = 968543943
#end_time = 971622087

# Set the ifos to analyse
ifos = ['H1','L1']

# Get segments and find where the data is
# NOTE: not all files are returned to top level, so all_files has some gaps
all_files = ahope.AhopeFileList([])
scienceSegs, segsDict = ahope.setup_segment_generation(workflow, ifos, 
                                            start_time, end_time, segDir, 
                                            maxVetoCat=5,
                                            minSegLength=2000)
datafind_files, scienceSegs = ahope.setup_datafind_workflow(workflow, 
                                            scienceSegs, dfDir, 
                                            checkSegmentGaps='update_times',
                                            checkFramesExist='warn')
all_files.extend(datafind_files)

# Template bank stuff
bank_files = ahope.setup_tmpltbank_workflow(workflow, scienceSegs, 
                                            datafind_files, 'datafind')
splitbank_files = ahope.setup_splittable_workflow(workflow, bank_files, 
                                                            'datafind')
all_files.extend(bank_files)
#NOTE: may want to remove splitbank if it confuses pipedown
all_files.extend(splitbank_files)

# setup the injection files
# FIXME: Pipedown expects the injections to have the random seed as a tag,
# here we just add that tag.
inj_files, inj_tags = ahope.setup_injection_workflow(workflow, scienceSegs, 
                                           datafind_files, splitbank_files, 
                                           start_time, end_time, 
                                           output_dir='inj_files', tags=['2134'])
timeSlideFiles = ahope.setup_timeslides_workflow(workflow, scienceSegs,
                                           output_dir='time_slide_files',
                                           timeSlideSectionName='tisi')

all_files.extend(inj_files)
tags = ["full_data"] + inj_tags
inj_files = [None] + inj_files
all_coincs = ahope.AhopeFileList([])
for inj_file, tag in zip(inj_files, tags):
    if not tag == 'full_data':
        timeSlideTags = ['zerolag']
    else:
        timeSlideTags = ['zerolag','slides']
    insps = ahope.setup_matchedfltr_workflow(workflow, scienceSegs, 
                                           datafind_files, splitbank_files, 
                                           tag, injection_file=inj_file,
                                           tags = [tag])
    all_files.extend(insps)
    coincs = ahope.setup_coincidence_workflow(workflow, scienceSegs, segsDict, 
                                        timeSlideFiles, insps, tag, tags=[tag],
                                        maxVetoCat=5,
                                        timeSlideTags=timeSlideTags)
    all_files.extend(coincs)
    all_coincs.extend(coincs)

pipedownParents = []
for coincFile in all_coincs:
    # Here I assume that no partitioned files are present
    pipedownParents.append(coincFile.node)

# Prepare the input for compatibility with pipedown

# Copy segment files
ifoString = ''.join(ifos)
for category in range(1, 6):
    ahopeVetoFile = segsDict[ifoString]['CUMULATIVE_CAT_%d' %(category)]
    ahopeVetoPath = ahopeVetoFile.path
    pipedownVetoFileName = '%s-VETOTIME_CAT_%d-%d-%d.xml' \
                            %(ifoString, category, start_time, \
                              end_time-start_time)
    pipedownVetoPath = os.path.join(segDir, pipedownVetoFileName)
    shutil.copyfile(ahopeVetoPath, pipedownVetoPath)
    

# Convert filelist to lal cache format
cacheFileList = all_files.convert_to_lal_cache()
cacheFileName = os.path.join(currDir, 'ihope_full_cache.cache')
cacheFileFP = open(cacheFileName, 'w')
cacheFileList.tofile(cacheFileFP)
cacheFileFP.close()

# Everything that follows is copied and modified from inspiralutils to allow us
# to run pipedown

# Make directory
pipedownDir = os.path.join(currDir, 'pipedown')
if not os.path.exists(pipedownDir+'/logs'):
    os.makedirs(pipedownDir+'/logs')
os.chdir(pipedownDir)

# Create the necessary ini file
# This is sufficiently different from the original ini file that some editing is
# required.
pipeCp = copy.deepcopy(workflow.cp)
# Create the condor sections
pipeCp.add_section("condor")
pipeCp.set("condor","universe","vanilla")
for item,value in pipeCp.items('executables'):
    pipeCp.set("condor", item, value)
    
# Create input section
pipeCp.add_section("input")
pipeCp.set("input","ihope-segments-directory","../segments")

# Write ini file to folder

iniFile = os.path.join(pipedownDir, 'pipedown.ini')
pipeCp.write(file(iniFile,"w"))

# Set up the command to run pipedown

pipeCommand = [pipeCp.get("condor","pipedown")]
pipeCommand.extend(["--log-path", log_directory])
pipeCommand.extend(["--config-file", iniFile])
pipeCommand.extend(["--gps-start-time", str(start_time)])
pipeCommand.extend(["--gps-end-time", str(end_time)])
pipeCommand.extend(["--ihope-cache", cacheFileName])
pipeCommand.extend(["--generate-all-data-plots"])

# run lalapps_pipedown
ahope.make_external_call(pipeCommand, outDir=pipedownDir + "/logs", 
                   outBaseName='pipedown_call')

# make pipedown job/node
pipeDag = iniFile.rstrip("ini") + "dag"
pipeJob = pipeline.CondorDAGManJob(pipeDag, pipedownDir)
pipeNode = pipeline.CondorDAGManNode(pipeJob)
workflow.dag.add_node(pipeNode)
if pipedownParents:
    for thisDag in pipedownParents:
        pipeNode.add_parent(thisDag)

# return to the original directory
os.chdir("..")

workflow.write_plans()
logging.info("Finished.")

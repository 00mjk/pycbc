#!/usr/bin/env python

# Copyright (C) 2013 Ian W. Harry
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

"""
Programe for running multi-detector ahope analysis through coincidence and then
generate post-processing and plots with pipedown.
This is designed to mimic the current behaviour of weekly_ihope.
"""
import pycbc
import pycbc.version
__author__  = "Ian Harry <ian.harry@astro.cf.ac.uk>"
__version__ = pycbc.version.git_verbose_msg
__date__    = pycbc.version.date
__program__ = "weekly_ahope"

import os, copy, shutil, argparse, ConfigParser, logging
from glue import segments
import pycbc.ahope as ahope
import Pegasus.DAX3 as dax

logging.basicConfig(format='%(asctime)s:%(levelname)s : %(message)s', 
                    level=logging.INFO)

_desc = __doc__[1:]
parser = argparse.ArgumentParser(description=_desc)
parser.add_argument('--version', action='version', version=__version__)
parser.add_argument("-d", "--output-dir", default=None,
                    help="Path to output directory.")
ahope.add_ahope_command_line_group(parser)
args = parser.parse_args()

workflow = ahope.AhopeWorkflow(args, 'weekly_ahope')

# Needed later for WIP
if args.output_dir:
    baseDir = args.output_dir
else:
    baseDir = os.getcwd()
runDir = os.path.join(baseDir, '%d-%d' %tuple(workflow.analysis_time))
if not os.path.exists(runDir):
    os.makedirs(runDir)
os.chdir(runDir)

currDir = os.getcwd()

segDir = os.path.join(currDir, "segments")
dfDir = os.path.join(currDir, "datafind")
fdDir = os.path.join(currDir, "full_data")
tsDir = os.path.join(currDir, "time_slide_files")
injDir = os.path.join(currDir, "inj_files")
ppDir = os.path.join(currDir, "ahope_postproc")
summ_dir = os.path.join(currDir, "summary")

# Get segments and find where the data is
# NOTE: not all files are returned to top level, so all_files has some gaps
all_files = ahope.AhopeFileList([])
scienceSegs, segsFileList = ahope.setup_segment_generation(workflow, segDir)
datafind_files, scienceSegs = ahope.setup_datafind_workflow(workflow, 
                                            scienceSegs, dfDir, segsFileList)
all_files.extend(datafind_files)

# Template bank stuff
bank_files = ahope.setup_tmpltbank_workflow(workflow, scienceSegs, 
                                            datafind_files, dfDir)

all_files.extend(bank_files)

# setup the injection files
# FIXME: Pipedown expects the injections to have the random seed as a tag,
# here we just add that tag.
inj_files, inj_tags = ahope.setup_injection_workflow(workflow,  
                                           output_dir=injDir, tags=['2134'])
timeSlideFiles = ahope.setup_timeslides_workflow(workflow,
                                           output_dir=tsDir,
                                           timeSlideSectionName='tisi')

all_files.extend(inj_files)
tags = ["full_data"] + inj_tags
output_dirs = [fdDir]
output_dirs.extend([os.path.join(currDir, tag) for tag in inj_tags])
all_coincs = ahope.AhopeFileList([])
for inj_file, tag, output_dir in zip([None]+inj_files, tags, output_dirs):
    if not tag == 'full_data':
        timeSlideTags = ['zerolag']
    else:
        timeSlideTags = ['zerolag','slides']
    insps = ahope.setup_matchedfltr_workflow(workflow, scienceSegs, 
                                           datafind_files, bank_files, 
                                           output_dir, injection_file=inj_file,
                                           tags = [tag])
    all_files.extend(insps)
    coincs = ahope.setup_coincidence_workflow(workflow, segsFileList,
                                        timeSlideFiles, insps, output_dir,
                                        tags=[tag], maxVetoCat=5,
                                        timeSlideTags=timeSlideTags)
    all_files.extend(coincs)
    all_coincs.extend(coincs)
    
    # Write the summary file if this is full_data   
    if tag == 'full_data':
        anal_log_files = ahope.setup_analysislogging(workflow, segsFileList,
                               insps, args, summ_dir, program_name=__program__)


# Set up ahope's post-processing, this is still incomplete

# FIXME: Don't like having to list this here!
ppVetoCats = [2,3,4] 

postProcPrepFiles = ahope.setup_postprocessing_preparation(workflow,
                      all_coincs, ppDir, injectionFiles=inj_files,
                      injectionTags=inj_tags, injLessTag='full_data',
                      vetoFiles=segsFileList, vetoCats=ppVetoCats)

postProcFiles = ahope.setup_postprocessing(workflow, postProcPrepFiles,
                                           anal_log_files, ppDir, tags=[],
                                           veto_cats=ppVetoCats)


# Also run pipedown, for legacy comparison

pipedownParents = []
for coincFile in all_coincs:
    # Here I assume that no partitioned files are present
    pipedownParents.append(coincFile.node)

# Dump out the formatted, combined ini file
workflow.cp.write(file("ahope_configuration.ini", "w"))

# Prepare the input for compatibility with pipedown
start_time = workflow.analysis_time[0]
end_time = workflow.analysis_time[1]

# Copy segment files
ifoString = workflow.ifo_string
for category in range(1, 6):
    vetoTag = 'CUMULATIVE_CAT_%d' %(category)
    ahopeVetoFile = segsFileList.find_output_with_tag(vetoTag)
    assert len(ahopeVetoFile) == 1
    ahopeVetoFile = ahopeVetoFile[0]
    ahopeVetoPath = ahopeVetoFile.storage_path
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
pipedown_log_dir = workflow.cp.get("ahope",'pipedown-log-path')

pipeCommand = [pipeCp.get("condor","pipedown")]
pipeCommand.extend(["--log-path", pipedown_log_dir])
pipeCommand.extend(["--config-file", iniFile])
pipeCommand.extend(["--gps-start-time", str(start_time)])
pipeCommand.extend(["--gps-end-time", str(end_time)])
pipeCommand.extend(["--ihope-cache", cacheFileName])
pipeCommand.extend(["--generate-all-data-plots"])

# run lalapps_pipedown
ahope.make_external_call(pipeCommand, out_dir=pipedownDir + "/logs", 
                   out_basename='pipedown_call')

# make pipedown job/node
pipeDag = iniFile.rstrip("ini") + "dag"
pipeDag_lfn = os.path.basename(pipeDag)
pipeNode = dax.DAG(pipeDag_lfn)

pipeNode.addProfile(dax.Profile("dagman", "DIR", pipedownDir))
subdag_file = dax.File(pipeDag_lfn)
subdag_file.PFN(pipeDag, site='local')
workflow._adag.addFile(subdag_file)
workflow._adag.addDAG(pipeNode)

if pipedownParents:
    for parent in pipedownParents:
        dep = dax.Dependency(parent=parent._dax_node, child=pipeNode)
        workflow._adag.addDependency(dep)

# return to the original directory
os.chdir("..")

# Set up for pipedown plotting

# Make directory
pipedownPlotDir = os.path.join(currDir, 'pipedown_plots')
if not os.path.exists(pipedownPlotDir+'/logs'):
    os.makedirs(pipedownPlotDir+'/logs')
os.chdir(pipedownPlotDir)

# Create the necessary ini file
# This is sufficiently different from the original ini file that some editing is
# required.
pipeCp = copy.deepcopy(workflow.cp)
# Create the condor sections
pipeCp.add_section("condor")
pipeCp.set("condor","universe","vanilla")
for item,value in pipeCp.items('executables'):
    pipeCp.set("condor", item, value)

# Write ini file to folder

iniFile = os.path.join(pipedownPlotDir, 'pipedown.ini')
pipeCp.write(file(iniFile,"w"))

# Set up command to run pipedown_plots

pipedown_log_dir = workflow.cp.get("ahope",'pipedown-log-path')
pipedown_tmp_space = workflow.cp.get("ahope",'pipedown-tmp-space')

for cat in ppVetoCats:
    veto_tag = "CUMULATIVE_CAT_%d" %(cat,)
    inputFiles = postProcFiles.find_output_with_tag(veto_tag)
    assert len(inputFiles) == 1
    inputFile = inputFiles[0]
    pipeCommand  = [pipeCp.get("condor","pipedown_plots")]
    pipeCommand.extend(["--tmp-space", pipedown_tmp_space])
    namingPrefix = "FULL_DATA_CAT_%d_VETO" %(cat,)
    pipeCommand.extend(["--naming-prefix", namingPrefix])
    pipeCommand.extend(["--instruments"] + workflow.ifos)
    pipeCommand.extend(["--gps-start-time", str(start_time)])
    pipeCommand.extend(["--gps-end-time", str(end_time)])
    pipeCommand.extend(["--input-file", inputFile.storage_path])
    pipeCommand.extend(["--ihope-cache", cacheFileName])
    pipeCommand.extend(["--simulation-tags"] + inj_tags)
    pipeCommand.extend(["--veto-category", str(cat)])
    pipeCommand.extend(["--log-path", pipedown_log_dir])
    pipeCommand.extend(["--config-file", iniFile])

    # run lalapps_pipedown
    ahope.make_external_call(pipeCommand, out_dir=pipedownPlotDir + "/logs",
                       out_basename='pipedown_plots_call')
    pipePlotDag = iniFile[0:-4] + "_" + namingPrefix + ".dag"
    pipePlot_lfn = os.path.basename(pipePlotDag)
    pipePlotNode = dax.DAG(pipePlot_lfn)
    
    workflow._adag.addDAG(pipePlotNode)
    dep = dax.Dependency(parent=inputFile.node._dax_node, child=pipePlotNode)
    workflow._adag.addDependency(dep)
    
    subdag_file = dax.File(pipePlot_lfn)
    subdag_file.PFN(pipePlotDag, site='local')
    workflow._adag.addFile(subdag_file)
    pipePlotNode.addProfile(dax.Profile("dagman", "DIR", pipedownPlotDir))


# return to the original directory
os.chdir("..")

# Setup for write_ihope_page

# Need to make an altered .ini file, start with the pipedown .ini as its closer
wipCp = copy.deepcopy(pipeCp)
# We hardcoded vetocat to 5 above, so do so again here until fixed
wipCp.add_section('segments')
wipCp.set('segments','veto-categories','2,3,4,5')
# Put the veto-definer in the expected location
vetoFile = wipCp.get('ahope-segments', 'segments-veto-definer-file')
vetoFileBase = os.path.basename(vetoFile)
# This line no longer needed as segment file is already there
#shutil.copyfile(vetoFile, os.path.join(currDir,'segments',vetoFileBase))
wipCp.set('segments', 'veto-def-file', vetoFileBase)
# Set the injection information
wipCp.remove_section('injections')
wipCp.add_section('injections')
for tag in inj_tags:
    wipCp.set('injections', tag.lower(), '')
# Write this ini file out
wipCp.write(file('ahope_config_wip.ini', 'w'))

# Need a second ini file with wip commands
wipConf = ConfigParser.ConfigParser()
wipConf.add_section('main')
wipConf.set('main', 'gps-start-time', str(start_time))
wipConf.set('main', 'gps-end-time', str(end_time))
wipConf.set('main', 'lead', 'Dotty Wot')
wipConf.set('main', 'second', 'Spotty Wot')
wipConf.set('main', 'title', 'Ahope coincidence analysis')
wipConf.set('main', 'notes', '')
wipConf.set('main', 'ihope-ini-file', 'ahope_config_wip.ini')
wipConf.set('main', 'ihope-directory', baseDir)
htmlOutDir = workflow.cp.get('ahope', 'ahope-html-basedir')
wipConf.set('main', 'html-directory', htmlOutDir)
# Here, for now, use installed version
wipConf.set('main', 'style', '/usr/share/lalapps/write_ihope_style.css')
wipConf.set('main', 'output', 'index.html')
wipConf.write(file('wip.ini', 'w'))

# Now add command to workflow
wip_exe = ahope.AhopeExecutable(workflow.cp, 'write_ihope_page')
wip_node = ahope.AhopeNode(wip_exe)
wip_node.add_opt('--config-file', os.path.join(currDir, 'wip.ini'))
wip_node.add_opt('--open-the-box')
wip_node.add_opt('--skip-followup')

workflow._adag.addJob(wip_node._dax_node)
wip_exe.insert_into_dax(workflow._adag)
dep = dax.Dependency(parent=pipeNode, child=wip_node._dax_node)
workflow._adag.addDependency(dep)

workflow.save()
logging.info("Written dax.")

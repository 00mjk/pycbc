##################################################################
Ahope: the inspiral analysis workflow generator (``pycbc.ahope``)
##################################################################

============
Introduction
============

Ahope is a tool used to create the workflows needed to perform coincident analyses of gravitational-wave data searching for compact-binary-coalescences using matched-filtering.

The ahope workflow runs through a number of stages, which are designed to be as independent of each other as possible, while also allowing an integrated end-to-end workflow to be constructed.

Documentation of the ahope executable and how to run it can be found here.

Each of the sections is described in detail below. Also refer to the `page here <https://www.lsc-group.phys.uwm.edu/ligovirgo/cbcnote/InspiralPipelineDevelopment/130627093845InspiralPipelineDocumentationAhope_development_plan>`_ for details. Also see the `link here <https://www.lsc-group.phys.uwm.edu/ligovirgo/cbcnote/InspiralPipelineDevelopment/130614025403InspiralPipelineDevelopmentThe%20evolution%20of%20ihope%20and%20inspiral>`_ for descriptions of what ahope should be and motivation for making ahope in the first place. **NOTE: REMOVE THESE LINKS ONCE AHOPE DOCUMENTATION IS SUFFICIENT THAT THIS IS NOT LONGER NEEDED**

====================
Examples
====================

Some examples of how to run ahope in different configurations can be found
in the source tree under::

    pycbc/ahope/ahope_examples

These examples are described in each section below

---------------------
data_checker
---------------------

This is an example of using only the segment query and datafind query modules
of ahope, with all checking options enabled. This will do the following

* Use the supplied information in the veto-definer file query for science times
* Using the veto-definer file query for CAT1,2,3,4,5 times
* Connect to the datafind server and query for frames at the times given in science - CAT1 (frame types provided in .ini file)
* Check that frames have been returned at all times that are given as science (-CAT1) by the segment server. Fail if not (this can be changed to update the science times, but here we want to fail if data is not present)
* Run os.path.is_file() on every frame file that was returned by datafind. This can be slow if run on long periods of time and if the fileservers are slow. Not recommended for a full ahope run at present, but useful for daily [a,i]hope runs.

This example can be edited for any time you are interested in and can be used to identify missing data before submitting a workflow. 

-------------------
daily_ahope
-------------------

This is an example of how to run an ahope workflow as far as it is coded. This
will:

* Get segments from the server, calculating CAT3 and above in the workflow for speed.
* Query the datafind server for frames.
* Create the template bank jobs needed to cover the times
* Split the template banks (into 2). This step could be easily removed, just delete this module in the python file and send the matched-filtering code the template bank input directly.
* Run the matched-filtering code on the split template banks
* Write a dax to file that can be submitted to run the workflow

This currently matches Chris' S6 test and works. Note that running this example (ie. time for the python code to do all of these steps and exit) takes approximately 1 minute to setup a workflow to analyse all of S6D. This is with the ping all frames step turned off, with this on we are seeing run times considerably longer.

-----------------------
er_daily_ahope
-----------------------

This is a more detailed example of daily_ahope. This will do the same things
as the daily_ahope example but then call into the remaining jobs, including
the daily_page dag generation, to set up a *complete* daily_ahope workflow.
This will also automatically generate the webpage at the end of the analysis.

====================
Initialization
====================

Take in command line input and the configuration file.

.. toctree::
   :maxdepth: 1

   ahope/initialization

====================
Obtaining data
====================

Determine what data is available and what veto flags are active and use this to construct analysis and veto segment lists. Also check the data exists on the machine that will be performing the analysis.

.. toctree::
   :maxdepth: 1

   ahope/segments

====================
Template bank
====================

Construct a template bank, or banks, of CBC waveforms that will be used to matched-filter the data with.

.. toctree::
   :maxdepth: 1 

   ahope/template_bank

====================
Matched-filtering
====================

Perform the matched-filters and calculate any signal-based consistency tests that should be calculated.

.. toctree::   :maxdepth: 1 

   ahope/matched_filter

====================
Coincidence
====================

Determine if "triggers" seen in one detector are also seen in other detectors. Also check for coincidence between time-slid triggers for background evaluation

.. toctree::   :maxdepth: 1 

   ahope/coincidence

====================
Post-processing
====================

Interpret the results, calculating false-alarm probabilities and rate limits.

.. toctree::   :maxdepth: 1 

   ahope/post_processing

====================
Plotting
====================

Create plots of the various outputs through the pipeline to easily enable the user to view results

.. toctree::   :maxdepth: 1

    ahope/plotting


====================
Generate html pages
====================


Tie the plots together in one html page, where *all* desired information should be available

.. toctree::   :maxdepth: 1

    ahope/web_pages


====================
Method documentation
====================

The documentation for all functions/modules within pycbc.ahope follows, unless you are looking for a specific function, it might be easier to navigate through the section links above.

.. toctree::
    pycbc.ahope

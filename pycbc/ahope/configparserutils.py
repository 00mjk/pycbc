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
This module provides a wrapper to the ConfigParser utilities for ahope
workflow construction. This module is described in the page here:
https://ldas-jobs.ligo.caltech.edu/~cbc/docs/pycbc/ahope/initialization_inifile.html
"""

import re
import distutils.spawn
import copy
import ConfigParser

class AhopeConfigParser(ConfigParser.SafeConfigParser):
    """
    This is a sub-class of ConfigParser.ConfigParser, which lets us add a few
    additional helper features that are useful in ahope.
    """
    def __init__(self, configFiles, overrideTuples, parsedFilePath=None):
        """
        Initialize an AhopeConfigParser. This reads the input configuration
        files, overrides values if necessary and performs the interpolation.
        See https://ldas-jobs.ligo.caltech.edu/~cbc/docs/pycbc/ahope/initialization_inifile.html
        
        Parameters
        -----------
        configFiles : Path to .ini file, or list of paths
            The file(s) to be read in and parsed.
        overrideTuples : List of (section, option, value) tuples
            Add the (section, option, value) triplets provided
            in this list to the provided .ini file(s). If the section, option
            pair is already present, it will be overwritten.
        parsedFilePath : Path, optional (default=None)
            If given, write the parsed .ini file back to disk at this location.

        Returns
        --------
        AhopeConfigParser
            Initialized AhopeConfigParser instance.
        """
        ConfigParser.SafeConfigParser.__init__(self)
        self.read_ini_file(configFiles)

        # Replace exe macros with full paths
        self.perform_exe_expansion()

        # Check for any substitutions that can be made
        # FIXME: The python 3 version of ConfigParser can do this automatically
        # move over to that if it can be backported to python2.X.
        # We use the same formatting as the new configparser module when doing
        # ExtendedInterpolation
        # This is described at
        # http://docs.python.org/3.4/library/configparser.html
        self.perform_extended_interpolation()

        # Split sections like [inspiral&tmplt] into [inspiral] and [tmplt]
        self.split_multi_sections()

        # Check for duplicate options in sub-sections
        self.sanity_check_subsections()

        # Dump parsed .ini file if needed
        if parsedFilePath:
            fp = open(parsedFilePath,'w')
            cp.write(fp)
            fp.close()


    def read_ini_file(self, cpFile):
        """
        Read a .ini file and return it as a ConfigParser class.
        This function does none of the parsing/combining of sections. It simply
        reads the file and returns it unedited

        Parameters
        ----------
        cpFile : Path to .ini file, or list of paths
            The path(s) to a .ini file to be read in

        Returns
        -------
        cp : ConfigParser
            The ConfigParser class containing the read in .ini file
        """

        # Read the file
        self.read(cpFile)


    def perform_exe_expansion(self):
        """
        This function will look through the executables section of the
        ConfigParser object and replace any values using macros with full paths.

        For any values that look like 

        ${which:lalapps_tmpltbank}

        will be replaced with the equivalent of which(lalapps_tmpltbank)

        Otherwise values will be unchanged.
        """
        # Only works on executables section
        for option, value in self.items('executables'):
            # Check the value
            newStr = self.interpolate_exe(value)
            if newStr != value:
                self.set('executables', option, newStr)


    def interpolate_exe(self, testString):
        """
        Replace testString with a path to an executable based on the format.

        If this looks like

        ${which:lalapps_tmpltbank}
 
        it will return the equivalent of which(lalapps_tmpltbank)

        Otherwise it will return an unchanged string.

        Parameters
        -----------
        testString : string
            The input string

        Returns
        --------
        newString : string
            The output string.
        """
        # First check if any interpolation is needed and abort if not
        testString = testString.strip()
        if not (testString.startswith('${') and testString.endswith('}')):
            return testString

        # This may not be an exe interpolation, so even if it has ${XXX} form
        # I may not have to do anything
        newString = testString

        # Strip the ${ and }
        testString = testString[2:-1]

        testList = testString.split(':')

        # Maybe we can add a few different possibilities for substitution
        if len(testList) == 2:
            if testList[0] == 'which':
                newString = distutils.spawn.find_executable(testList[1])

        return newString


    def perform_extended_interpolation(self):
        """
        Filter through an ini file and replace all examples of 
        ExtendedInterpolation formatting with the exact value. For values like
        ${example} this is replaced with the value that corresponds to the
        option called example ***in the same section***

        For values like ${common|example} this is replaced with the value that
        corresponds to the option example in the section [common]. Note that
        in the python3 config parser this is ${common:example} but python2.7
        interprets the : the same as a = and this breaks things

        Nested interpolation is not supported here.
        """

        # Do not allow any interpolation of the section names
        for section in self.sections():
            for option,value in self.items(section):
                # Check the option name
                newStr = self.interpolate_string(option, section)
                if newStr != option:
                    self.set(section,newStr,value)
                    self.remove_option(section,option)
                # Check the value
                newStr = self.interpolate_string(value, section)
                if newStr != value:
                    self.set(section,option,newStr)


    def interpolate_string(self, testString, section):
        """
        Take a string and replace all example of ExtendedInterpolation
        formatting within the string with the exact value. 

        For values like ${example} this is replaced with the value that
        corresponds to the option called example ***in the same section***

        For values like ${common|example} this is replaced with the value that
        corresponds to the option example in the section [common]. Note that
        in the python3 config parser this is ${common:example} but python2.7
        interprets the : the same as a = and this breaks things

        Nested interpolation is not supported here.

        Parameters
        ----------
        testString : String
            The string to parse and interpolate
        section : String
            The current section of the ConfigParser object

        Returns
        ----------
        testString : String
            Interpolated string
        """

        # First check if any interpolation is needed and abort if not
        reObj = re.search(r"\$\{.*?\}", testString)
        while reObj:
            # Not really sure how this works, but this will obtain the first
            # instance of a string contained within ${....}
            repString = (reObj).group(0)[2:-1]
            # Need to test which of the two formats we have
            splitString = repString.split('|')
            if len(splitString) == 1:
                try:
                    testString = testString.replace('${'+repString+'}',\
                                            self.get(section,splitString[0]))
                except ConfigParser.NoOptionError:
                    print "Substitution failed"
                    raise
            if len(splitString) == 2:
                try:
                    testString = testString.replace('${'+repString+'}',\
                                       self.get(splitString[0],splitString[1]))
                except ConfigParser.NoOptionError:
                    print "Substitution failed"
                    raise
            reObj = re.search(r"\$\{.*?\}", testString)

        return testString


    def split_multi_sections(self):
        """
        Parse through the AhopeConfigParser instance and splits any sections
        labelled with an "&" sign (for e.g. [inspiral&tmpltbank]) into
        [inspiral] and [tmpltbank] sections. If these individual sections
        already exist they  will be appended to. If an option exists in both the
        [inspiral] and [inspiral&tmpltbank] sections an error will be thrown
        """
        # Begin by looping over all sections
        for section in self.sections():
            # Only continue if section needs splitting
            if '&' not in section:
                continue
            # Get list of section names to add these options to
            splitSections = section.split('&')
            for newSec in splitSections:
                # Add sections if they don't already exist
                if not self.has_section(newSec):
                    self.add_section(newSec)
                self.add_options_to_section(newSec, self.items(section))
            self.remove_section(section)


    def add_options_to_section(self ,section, items, overwrite_options=False):
        """
        Add a set of options and values to a section of a ConfigParser object.
        Will throw an error if any of the options being added already exist,
        this behaviour can be overridden if desired

        Parameters
        ----------
        section : string
            The name of the section to add options+values to
        items : list of tuples
            Each tuple contains (at [0]) the option and (at [1]) the value to
            add to the section of the ini file
        overwrite_options : Boolean, optional
            By default this function will throw a ValueError if an option exists
            in both the original section in the ConfigParser *and* in the
            provided items.
            This will override so that the options+values given in items
            will replace the original values if the value is set to True.
            Default = True 
        """
        # Sanity checking
        if not self.has_section(section):
            raise ValueError('Section %s not present in ConfigParser.' \
                             %(section,))

        # Check for duplicate options first
        for option,value in items:
            if not overwrite_options:
                if option in self.options(section):
                    raise ValueError('Option exists in both original ' + \
                                  'ConfigParser and input list: %s' %(option,))
            self.set(section,option,value)


    def sanity_check_subsections(self):
        """
        This function goes through the ConfigParset and checks that any options
        given in the [SECTION_NAME] section are not also given in any 
        [SECTION_NAME-SUBSECTION] sections.

        """
        # Loop over the sections in the ini file
        for section in self.sections():
            # Loop over the sections again
            for section2 in self.sections():
                # Check if any are subsections of section
                if section2.startswith(section + '-'):
                    # Check for duplicate options whenever this exists
                    self.check_duplicate_options(section, section2,
                                                 raise_error=True)


    def check_duplicate_options(self, section1, section2, raise_error=False):
        """
        Check for duplicate options in two sections, section1 and section2.
        Will return a list of the duplicate options.
    
        Parameters
        ----------
        section1 : string
            The name of the first section to compare
        section2 : string
            The name of the second section to compare
        raise_error : Boolean, optional (default=False)
            If True, raise an error if duplicates are present.

        Returns
        ----------
        duplicate : List
            List of duplicate options
        """
        # Sanity checking
        if not self.has_section(section1):
            raise ValueError('Section %s not present in ConfigParser.'\
                             %(section1,) )
        if not self.has_section(section2):
            raise ValueError('Section %s not present in ConfigParser.'\
                             %(section2,) )

        items1 = self.options(section1)
        items2 = self.options(section2)

        # The list comprehension here creates a list of all duplicate items
        duplicates = [x for x in items1 if x in items2]

        if duplicates and raise_error:
            raise ValueError('The following options appear in both section ' +\
                             '%s and %s: %s' \
                             %(section1,section2,' '.join(duplicates)))

        return duplicates



    def get_opt_tag(self, section, option, tag):
        """
        Supplement to ConfigParser.ConfigParser.get(). This will search for an
        option in [section] and if it doesn't find it will also try in
        [section-tag]. This is appended to the ConfigParser class. Will raise a
        NoSectionError if [section] doesn't exist. Will raise NoOptionError if
        option is not found in [section] and [section-tag] doesn't exist or does
        not have the option.

        Parameters
        -----------
        self : ConfigParser object
            The ConfigParser object (automatically passed when this is appended
            to the ConfigParser class)
        section : string
            The section of the ConfigParser object to read
        option : string
            The ConfigParser option to look for
        tag : string
            The name of the subsection to look in, if not found in [section]
 
        Returns
        --------
        string
            The value of the options being searched for
        """
        # Need lower case tag name
        if tag:
            tag = tag.lower()

        try:
            return self.get(section,option)
        except ConfigParser.Error:
            errString = "No option '%s' in section '%s' " %(option,section)
            if not tag:
                raise ConfigParser.Error(errString + ".")
            if self.has_section('%s-%s' %(section, tag)):
                if self.has_option('%s-%s' %(section, tag),option):
                    return self.get('%s-%s' %(section, tag),option)
                else:
                    errString+= "or in section '%s-%s'." %(section, tag)
                    raise ConfigParser.Error(errString)
            else:
                errString += "and section '%s-%s' does not exist."\
                             %(section, tag)
                raise ConfigParser.Error(errString)

    def get_opt_tags(self, section, option, tags):
        """
        Supplement to ConfigParser.ConfigParser.get(). This will search for an
        option in [section] and if it doesn't find it will also try in
        [section-tag] for every value of tag in tags.
        Will raise a
        NoSectionError if [section] doesn't exist. Will raise NoOptionError if
        option is not found in [section] and [section-tags]
        doesn't exist or does not have the option.

        Parameters
        -----------
        self : ConfigParser object
            The ConfigParser object (automatically passed when this is appended
            to the ConfigParser class)
        section : string
            The section of the ConfigParser object to read
        option : string
            The ConfigParser option to look for
        tag : string
            The name of the subsection to look in, if not found in [section]
 
        Returns
        --------
        string
            The value of the options being searched for
        """
        try:
            return self.get(section, option)
        except ConfigParser.Error:
            errString = "No option '%s' in section [%s] " %(option,section)
            if not tags:
                raise ConfigParser.Error(errString + ".")
            returnVals = []
            sectionList = ["%s-%s" %(section, tag) for tag in tags]
            for tag in tags:
                if self.has_section('%s-%s' %(section, tag)):
                    if self.has_option('%s-%s' %(section, tag), option):
                        returnVals.append(self.get('%s-%s' %(section, tag),
                                                    option))
            if not returnVals:
                errString += "or in sections [%s]." %("] [".join(sectionList))
                raise ConfigParser.Error(errString)
            if len(returnVals) > 1:
                errString += "and multiple entries found in sections [%s]."\
                              %("] [".join(sectionList))
                raise ConfigParser.Error(errString)
            return returnVals[0]


    def has_option_tag(self, section, option, tag):
        """
        Supplement to ConfigParser.ConfigParser.has_option().
        This will search for an
        option in [section] and if it doesn't find it will also try in
        [section-tag]. Will return True if it finds the option and false if
        not.

        Parameters
        -----------
        self : ConfigParser object
            The ConfigParser object (automatically passed when this is appended
            to the ConfigParser class)
        section : string
            The section of the ConfigParser object to read
        option : string
            The ConfigParser option to look for
        tag : string
            The name of the subsection to look in, if not found in [section]
 
        Returns
        --------
        Boolean
            Is the option in the section or [section-tag]
        """
        try:
            self.get_opt_tag(section, option, tag)
            return True
        except ConfigParser.Error:
            return False

    def has_option_tags(self, section, option, tags):
        """
        Supplement to ConfigParser.ConfigParser.has_option().
        This will search for an
        option in [section] and if it doesn't find it will also try in
        [section-tag] for each value in tags.
        Will return True if it finds the option and false if not.

        Parameters
        -----------
        self : ConfigParser object
            The ConfigParser object (automatically passed when this is appended
            to the ConfigParser class)
        section : string
            The section of the ConfigParser object to read
        option : string
            The ConfigParser option to look for
        tags : list of strings
            The names of the subsection to look in, if not found in [section]
 
        Returns
        --------
        Boolean
            Is the option in the section or [section-tag] (for tag in tags)
        """
        try:
            self.get_opt_tag(section, option, tags)
            return True
        except ConfigParser.Error:
            return False


from glue import segments

class TmpltbankList:
    '''This class holds a list of Tmpltbank objects. It inherits from the
    built-in list class, but also allows a number of features. ONLY Tmpltbank
    instances should be within a TmpltbankList instance.
    '''

    def __init__(self,*args):
        '''
        Initialize the list. Any kwargs are sent directly to
        list.__init__().
        '''
 
        list.__init__(self, *args)

    def find_bank(self,ifo,time):
        '''Return template bank that covers the given time, or is most
        appropriate for the supplied time range.

        Parameters
        -----------
        ifo : string
           Name of the ifo that the bank should correspond to
        time : int/float/LIGOGPStime or tuple containing two values
           If int/float/LIGOGPStime (or similar may of specifying one time) is
           given, return the bank corresponding to the time. This calls
           self.find_bank_at_time(ifo,time).
           If a tuple of two values is given, return the bank that is **most
           appropriate** for the time range given. This calls
           self.find_bank_in_range

        Returns
        --------
        bank : Tmpltbank class
           The bank that corresponds to the time/time range
        '''
        # Determine whether I have a specific time, or a range of times
        try:
            # This is if I have a range of times
            if len(time) == 2:
                bank = self.find_bank_in_range(ifo,time[0],time[1])
        except TypeError:
            # This is if I have a single time
            bank = self.find_bank_at_time(ifo,time)                
        else:
            # This is if I got a list that had more (or less) than 2 entries
            if len(time) != 2:
                raise TypeError("I do not understand the input variable time")
        return bank

    def find_bank_at_time(self,ifo,time):
       '''Return template bank that covers the given time.

        Parameters
        -----------
        ifo : string
           Name of the ifo that the bank should correspond to
        time : int/float/LIGOGPStime
           Return the bank that covers the supplied time. If no bank covers
           the time this will return None. If more than one bank covers the
           time a ValueError will be raised. Banks must cover exclusive times.

        Returns
        --------
        bank : Tmpltbank class
           The bank that corresponds to the time.
        '''
       # Get list of banks that overlap time, for given ifo
       banks = [i for i in self if ifo == i.get_ifo() and time in i.get_time()] 
       if len(banks == 0):
           # No bank at this time
           return None
       elif len(banks == 1):
           # 1 bank at this time (good!)
           return banks
       else:
           raise ValueError("%d banks overlap this time. Banks are supposed"+\
                            "to cover exclusive times.")

    def find_bank_in_range(self,ifo,start,end):
        '''Return template bank that is most appropriate for the supplied
        time range. That is, the bank whose coverage time has the largest
        overlap with the supplied time range. If no banks overlap the supplied
        time window, will return None. Banks should cover exclusive times,
        although this function does not check for that.

        Parameters
        -----------
        ifo : string
           Name of the ifo that the bank should correspond to
        start : int/float/LIGOGPStime 
           The start of the time range of interest.
        end : int/float/LIGOGPStime
           The end of the time range of interest

        Returns
        --------
        bank : Tmpltbank class
           The bank that is most appropriate for the time range'''
        # First filter banks corresponding to ifo
        banks = [i for i in self if ifo == i.get_ifo()] 
        if len(banks == 0):
            # No banks correspond to that ifo
            return None
        # Filter banks to those overlapping the given window
        currSeg = segments.segment([start,end])
        currSegList = segments.segmentlist([currSeg])
        banks = [i for i in banks if i.get_time.intersects(currSeg)]
        if len(banks == 0):
            # No banks overlap that time period
            return None
        elif len(banks == 1):
            # One bank overlaps that period
            return banks[0]
        else:
            # More than one bank overlaps period
            # Find lengths of overlap between time window and bank window
            overlapWindows = [abs(i.get_time() & currSegList) for i in banks]
            # Return the bank with the biggest overlap
            overlapWindows = numpy.array(overlapWindows,dtype = int)
            return banks[overlapWindows.argmax()]


class Tmpltbank:
    '''This class holds the details of an individual template bank. This
    template bank may be pre-supplied, generated from within the ahope command
    line script, or generated within the workflow. This stores 4 pieces of
    information, which will be used in later stages of the workflow, these are:

    * The location of the template bank (which may not yet exist)
    * The ifo that the bank is valid for
    * The time span that the bank is valid for
    * The dax job that will generate the bank (if appropriate)
    '''

    def __init__(self,bank=None,ifo=None,time=None,job=None):
        # Set everything to None to start
        self.__bank = None
        self.__ifo = None
        self.__time = None
        self.__job = None
        
        # Parse and set kwargs if given
        if bank:
            self.set_bank(bank)
        if ifo:
            self.set_ifo(ifo)
        if time:
            self.set_time(time)
        if job:
            self.set_job(job)

    def get_bank():
        '''Return self.__bank if it has been set, fail if not.

        Parameters
        ----------
        None

        Returns
        ----------
        bank : string
          The location of the template bank file, this may not
          exist yet if the bank will be
          generated by the workflow. In that case
          this gives the location that the bank will be written to.
          Will fail if the bank has not yet been set.
        '''
        if self.__bank:
            return self.__bank
        else:
            raise ValueError("Bank has not been set for this instance.")

    def set_bank(bank):
        '''Set self.__bank to bank.

        Parameters
        ----------
        bank : string
           The location of the template bank file, this may not
           exist yet if the bank will be generated by the workflow.

        Returns
        ----------
        None
        '''
        self.__bank = bank

    def get_ifo():
        '''Return self.__ifo if it has been set, Fail if not.

        Parameters
        ----------
        None

        Returns
        ----------
        ifo : string
           The ifo that the template bank is intended to be used
           for. If a bank (such as a pregenerated bank) is intended for **all**
           ifos then you should create multiple
           Tmpltbank classes, each with a different
           ifo. Will fail if the ifo has not yet been set.
        '''
        if self.__ifo:
            return self.__ifo
        else:
            raise ValueError("ifo has not been set for this instance.")

    def set_ifo(ifo):
        '''Set self.__ifo to ifo.

        Parameters
        ----------
        ifo : string
           Sets the ifo used for this bank

        Returns
        ----------
        None
        '''
        self.__ifo = ifo

    def get_time():
        '''Return self.__time if it has been set, fail if not.

        Parameters
        ----------
        None

        Returns
        ----------
        time : glue.ligolw segmentlist
           This is the time for
           which the template bank should be valid.
           The bank may be generated using data that covers
           part of this time, or even a completely
           different time. This simply says
           that during the times given in the segmentlist,
           this template bank is the preferred one to use.
           Will fail if the time has not yet been set.
        '''
        if self.__time:
            return self.__time
        else:
            raise ValueError("ifo has not been set for this instance.")

    def set_time(time):
        '''Set self.__time to time.

        Parameters
        ----------
        time : glue.ligolw segmentlist
           Sets the time for which the template bank is valid.

        Returns
        ----------
        None
        '''
        if type(time) != segments.segmentlist:
            raise TypeError("Variable supplied to Tmpltbank.set_time() must "+\
                            "be a glue.segment.segmentlist class.")
        self.__time = time

    def get_job(job):
        '''Return self.__job if it has been set, Fail if not.

        Parameters
        ----------
        None

        Returns
        ----------
        job : Condor job
           This is the the condor job that will generate the template
           bank. If no job has been set, this
           will return None. For the case where
           the bank will not be generated from
           within the workflow, this should not be set.
        '''
        return self.__job

    def set_job(job):
        '''Set self.__job to job.

        Parameters
        ----------
        job : Condor job
           Sets the condor job that will run the template bank.

        Returns
        ----------
        None

        '''
        # FIXME: What sanity check is appropriate here?
        self.__job = job

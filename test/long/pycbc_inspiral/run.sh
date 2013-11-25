#set path to here
PATH=$PWD:$PATH

#run pycbc_inspiral
sh prun.sh

#run lalapps_inspiral
sh lrun.sh

#compare the preconditioning
python cond-check.py

#separately compare the psd generation
python psd-check.py

#!/usr/local/bin/python -u

import sys,os,logging,re,traceback
sys.path.append("/usr/local/bin/pymodules")
from emgenutil import EXENAME,EXEPATH,GeneralError
import emgenutil

#------------------------------------------------------------------------------
# GLOBALS
#------------------------------------------------------------------------------

logger=logging.getLogger(EXENAME)
G_myGlobalVar = 'abc'

#------------------------------------------------------------------------------
# USAGE
#------------------------------------------------------------------------------

def usage():
   from string import Template
   usagetext = """

 $EXENAME

 Function: Whatever

 Syntax  : $EXENAME {--debug #}

 Note    : Parm       Description
           ---------- --------------------------------------------------------
           --debug    optionally specifies debug option
                      0=off 1=STDERR 2=FILE

 Examples: $EXENAME

 Change History:
  em  XX/XX/2016  first written
.
"""
   template = Template(usagetext)
   return(template.substitute({'EXENAME':EXENAME}))


#------------------------------------------------------------------------------
# Subroutine: main
# Function  : Main routine
# Parms     : none (in sys.argv)
# Returns   : nothing
# Assumes   : sys.argv has parms, if any
#------------------------------------------------------------------------------
def main():

   ##############################################################################
   #
   # Main - initialize
   #
   ##############################################################################

   initialize()

   ##############################################################################
   #
   # Logic
   #
   ##############################################################################

   try:

      # Example use of config file options.
      if 'simpleoption' in G_config:
         print("simpleoption:", G_config['simpleoption'])
      if 'listoption' in G_config:
         print("listoption:", G_config['listoption'])
      if 'dictoption' in G_config:
         print("dictoption:", G_config['dictoption'])

      (returncode,cmdoutput,cmderror) = emgenutil.execCommand("/bin/ls -l "+emgenutil.G_options.myrequiredarg)

      if returncode == 0:
         for line in cmdoutput.splitlines():
            print("line:",line)
      else:
         raise GeneralError('execCommand non-Zero returncode: %d\nSTDERR:\n%s' % (returncode,cmderror))


   except GeneralError as e:
      if emgenutil.G_options.debug:
         # Fuller display of the Exception type and where the exception occured in the code
         (eType, eValue, eTraceback) = sys.exc_info()
         tbprintable = ''.join(traceback.format_tb(eTraceback))
         emgenutil.exitWithErrorMessage("%s Exception: %s\n%s" % (eType.__name__, eValue, tbprintable), errorCode=e.errorCode)
      else:
         emgenutil.exitWithErrorMessage(e.message, errorCode=e.errorCode)

   except Exception as e:
      if emgenutil.G_options.debug:
         # Fuller display of the Exception type and where the exception occured in the code
         (eType, eValue, eTraceback) = sys.exc_info()
         tbprintable = ''.join(traceback.format_tb(eTraceback))
         emgenutil.exitWithErrorMessage("%s Exception: %s\n%s" % (eType.__name__, eValue, tbprintable))
      else:
         emgenutil.exitWithErrorMessage(str(e))

   ##############################################################################
   #
   # Finish up
   #
   ##############################################################################

   logger.info(EXENAME+" exiting")
   logging.shutdown()

   exit()


#------------------------------------------------------------------------------
# Subroutine: initialize
# Function  : performs initialization of variable, CONSTANTS, other
# Parms     : none
# Returns   : nothing
# Assumes   : ARGV has parms, if any
#------------------------------------------------------------------------------
def initialize():

   # PROCESS COMMAND LINE PARAMETERS

   import argparse  # http://www.pythonforbeginners.com/modules-in-python/argparse-tutorial/

   parser = argparse.ArgumentParser(usage=usage())
   parser.add_argument('myrequiredarg')                        # positional, required
   parser.add_argument('myoptionalarg', nargs='?')             # positional, optional
   parser.add_argument('myremainingoptionalargs', nargs='*')   # positional, optional, zero OR MORE
   parser.add_argument('--debug', dest="debug", type=int, help='0=no debug, 1=STDERR, 2=log file')
   parser.add_argument('-o', '--option1', action="store_true", dest="option1", help='help for this option')

   emgenutil.G_options = parser.parse_args()

   if emgenutil.G_options.debug == None or emgenutil.G_options.debug == 0:
      logging.disable(logging.CRITICAL)  # effectively disable all logging
   else:
      if emgenutil.G_options.debug == 9:
         emgenutil.configureLogging(loglevel='DEBUG')
      else:
         emgenutil.configureLogging()

   if emgenutil.G_options.option1:
      logger.info("option1 is true")

   if emgenutil.G_options.myoptionalarg: logger.info("myoptionalarg: "+emgenutil.G_options.myoptionalarg)
   if emgenutil.G_options.myremainingoptionalargs: logger.info("myremainingoptionalargs"+str(emgenutil.G_options.myremainingoptionalargs))

   global G_config
   G_config = emgenutil.processConfigFile()

   logger.info(EXENAME+" starting:"+__name__+" with these args:"+str(sys.argv))

# Standard boilerplate to call the main() function to begin the program.
if __name__ == "__main__":
   main()


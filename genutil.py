#!/usr/local/bin/python
###########################################################################
#
# genutil.py
#
# Function: Python Utility functions
#
# Change History:
#  em  03/26/2016  first written
#
###########################################################################
#
import sys,os,logging,subprocess,re,datetime,yaml

# Import smtplib for the actual sending function
import smtplib

# Import the email modules we'll need
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email import encoders

# import socket for singleton lock
import socket

import twitter

#------------------------------------------------------------------------------
# CLASSES
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
# Class: GeneralError
# Function  : Handle exceptions raised for general errors encountered
# Parms     : message - some error message string
#             errorCode - an optional HTTP Error code
# Returns   : __str__ returns an appropriate error message
# Assumes   :
#------------------------------------------------------------------------------
class GeneralError(Exception):
   def __init__(self, message, errorCode="400 Bad Request"):
       self.message = message
       self.errorCode = errorCode
   def __str__(self):
      return "Error encountered!  %s  errorCode=%s." % (self.message, self.errorCode)

#------------------------------------------------------------------------------
# GLOBALS
#------------------------------------------------------------------------------

logger=logging.getLogger(__name__)

G_options = None  # options from the cmd line (argparse object)
G_config  = {}    # options from the script's ini file

(EXEPATH,EXENAME) = os.path.split(sys.argv[0])
EXEPATH += os.sep

#------------------------------------------------------------------------------
# Function  : configureLogging
# Function  : configures the Logging for this execution of the program
# Parms     : logdestination = (optional) 'STDERR' or the name of a file to log to
#                 defaults to sys.argv[0].log
#             loglevel = lowest level of message to log.
#                 defaults to 'INFO'
# Returns   : nothing
# Assumes   : G_option.debug is set
#------------------------------------------------------------------------------
def configureLogging(logdestination=sys.argv[0]+'.log',loglevel='INFO'):
   if G_options.debug == 1:
      logging.basicConfig(
         format='%(asctime)s %(name)s:%(lineno)i %(levelname)s %(message)s',
         datefmt='%m/%d/%Y %H:%M:%S',
         level=getattr(logging, loglevel.upper())
      )
   else:
      # Need to do this vs. using basicConfig because we need latin-1 encoding to prevent unexpected data errors writing to the log
      root_logger= logging.getLogger()
      root_logger.setLevel(getattr(logging, loglevel.upper()))
      handler = logging.FileHandler(logdestination, 'w', 'latin-1')
      formatter = logging.Formatter('%(asctime)s %(name)s:%(lineno)i %(levelname)s %(message)s')
      handler.setFormatter(formatter)
      root_logger.addHandler(handler)

#------------------------------------------------------------------------------
# Function  : execCommand
# Function  : executes a shell command
# Parms     : cmd = string, command(s) to exec (can be anything that the shell will accept)
# Returns   : tuple: (returncode,stdout,stderr)
# Assumes   :
#------------------------------------------------------------------------------
def execCommand(cmd):

   proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
   (out, err) = proc.communicate()
   return(proc.returncode,out,err)



#------------------------------------------------------------------------------
# Function  : processConfigFile
# Function  : Reads Config file and establishes G_config dict with values.
#             Config file is yaml syntax.
# Parms     : none
# Returns   : data structure as per the yaml load
# Assumes   : Config file is in the same dir as executable and named $EXENAME.yaml
#
# Example of what calling module can do with G_config
#  for key in genutil.G_config:
#     print(key+":"+genutil.G_config[key]+".")
#  mylist = genutil.G_config['listoption'].splitlines()
#  print(mylist)
#
#------------------------------------------------------------------------------
def processConfigFile(configFile=sys.argv[0]+".yaml"):

   if not os.path.isfile(configFile):
      exitWithErrorMessage("config file "+configFile+" not found.",2);

   config = loadYaml(configFile)

   for key in config:
      logger.info("config["+key+"]:"+str(config[key])+".")

   return config


#------------------------------------------------------------------------------
# Function  : ping
# Function  : Attempt to ping a device.
# Parms     : nameOrIP - hostname or IP adddress
#             count - # of pings to try (optional)
# Returns   : True (responded to ping) or False (100% packet loss)
# Assumes   :
#------------------------------------------------------------------------------
def ping(nameOrIP,count=2):

   cmd = '/bin/ping -c%d %s' % (count, nameOrIP)

   proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
   (out, err) = proc.communicate()

   #print(out)

   if " 100% packet loss" in out or "unknown host" in err:
      return False

   if "%d packets transmitted" % count in out:
      return True

   exitWithErrorMessage("ERROR: unexpected results from ping.  %s" % out)


#------------------------------------------------------------------------------
# Function  : getLock
# Function  : Attempt to get a lock on a given lock name.
# Parms     : lockName - a unique string to represent the lock
# Returns   : nothing.  Raises a GeneralError if the lock cannot be obtained.
# Assumes   : This will only be used for a single held lock at a time.
#             A freeLock must be done before obtaining a new lock.
#------------------------------------------------------------------------------
import socket
def getLock(lockName):
  global G_lockSocket   # Without this our lock gets garbage collected (refereneced by freeLock too)
  G_lockSocket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
  try:
    G_lockSocket.bind('\0' + lockName)
    logger.info('Lock %s successfully obtained.' % lockName)
  except socket.error as e:
    logger.info('Lock %s exists so another script must have it.' % lockName)
    raise GeneralError("Lock %s already in use." % lockName)

#------------------------------------------------------------------------------
# Function  : getLock
# Function  : Frees the lock obtained by getLock
# Parms     : none
# Returns   : nothing
# Assumes   : G_lockSocket is the socket created by getLock.
#------------------------------------------------------------------------------
def freeLock():
   G_lockSocket.shutdown(socket.SHUT_RDWR)
   G_lockSocket.close()


#------------------------------------------------------------------------------
# Function  : loadYaml
# Function  : Load yaml data from a file
# Parms     : filepath - file path to yaml file
# Returns   : data structure as per the yaml file
# Assumes   :
#------------------------------------------------------------------------------
def loadYaml(filepath):
   with open(filepath, "r") as INFILE:
      data = yaml.load(INFILE)
   return data


#------------------------------------------------------------------------------
# Function  : sendEmail
# Function  : Send an email with optional file attachment
# Parms     : emailTo   email address of "to" person
#             subject   Subject text
#             bodyText  Body text (new lines are line breaks)
#             bodyHtml        (optional) Body text in HTML markup
#             binaryFilepath  (optional) filepath of attachment
#             emailFrom       (optional) "from" email (defaults to donotreply@<hostname>
# Returns   : data structure as per the yaml file
# Assumes   :
#------------------------------------------------------------------------------
def sendEmail(emailTo, subject, bodyText, bodyHtml=None, binaryFilepath=None, emailFrom='default'):

   #---------------------------------------------------------------------------
   # Send an email with a file attachment
   #---------------------------------------------------------------------------

   if emailFrom == 'default':
      hostname   = os.uname().nodename
      emailFrom  = 'donotreply@%s' % hostname

   # Create the enclosing (outer) message
   msg = MIMEMultipart()
   msg['Subject'] = subject
   msg['To'] = emailTo
   msg['From'] = emailFrom
   msg.preamble = 'You will not see this in a MIME-aware mail reader.\n'
   msg.attach(MIMEText(bodyText))
   if bodyHtml:
   		msg.attach(MIMEText(bodyHtml,'html'))

   if binaryFilepath:
      ctype = 'application/octet-stream'
      maintype, subtype = ctype.split('/', 1)
      with open(binaryFilepath,"rb") as INFILE:
         fileAttachment = MIMEBase(maintype, subtype)
         fileAttachment.set_payload(INFILE.read())

      # Encode the payload using Base64
      encoders.encode_base64(fileAttachment)

      # Set the filename parameter and attach file to outer message
      fileAttachment.add_header('Content-Disposition', 'attachment', filename=binaryFilepath)
      msg.attach(fileAttachment)
      msg.attach(MIMEText('This file is attached: %s' % binaryFilepath))

   # Now send the message
   mailServer = smtplib.SMTP('smtp.gmail.com:587')
   mailServer.starttls()
   mailServer.login(G_config['sendEmail']['gmailUsername'],G_config['sendEmail']['gmailPassword'])

   mailServer.sendmail(emailFrom, emailTo, msg.as_string())
   mailServer.quit()


#------------------------------------------------------------------------------
# Function  : sendTwitterDirectMessage
# Function  : Send an Twitter Direct Message with optional file attachment
# Parms     : toTwitterName   Twitter Name of recepient
#             messageText     Text of message to sent
#             binaryFilepath  (optional) filepath of attachment
# Returns   : nothing
# Assumes   : yaml file has Twitter API info
#------------------------------------------------------------------------------
def sendTwitterDirectMessage(toTwitterName, messageText, binaryFilepath=None):
   
   api = twitter.Api(consumer_key=G_config["twitterAccount"]["consumerKey"],
                     consumer_secret=G_config["twitterAccount"]["consumerSecret"],
                     access_token_key=G_config["twitterAccount"]["accessToken"],
                     access_token_secret=G_config["twitterAccount"]["accessTokenSecret"],
                     sleep_on_rate_limit=True)
   
   api.PostDirectMessage(messageText, user_id=None, screen_name=toTwitterName)


#------------------------------------------------------------------------------
# Subroutine: exitWithErrorMessage
# Function  : Print an appropriate error response to stdout/stderr and then exit
# Parms     : message - a text message
#             errorCode - optional errorcode text, defaults
# Returns   : Exits after printing results to STDERR
# Assumes   :
#------------------------------------------------------------------------------
def exitWithErrorMessage(message, errorCode="400 Bad Request", exitcode=1):

   logging.error("Error: "+message)
   print("Error: "+message, file=sys.stderr)
   exit(exitcode)


#------------------------------------------------------------------------------
# Initialize
#------------------------------------------------------------------------------

#G_config = loadYaml(EXEPATH+"genutil.py.yaml")
G_config = loadYaml("%spymodules/genutil.py.yaml" % (EXEPATH))

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------

if __name__ == "__main__":

   import time

   print("Starting...");
   print("Config items: %s" % str(G_config))

   print("Sending Twitter DM...")
   sendTwitterDirectMessage(sys.argv[1], "Hellooo there!")

   print("Sending a test email...")
   subject = 'This is a test email sent at %s!' % datetime.datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
   bodyText = "This is the body\nAnd more"
   emailTo = "edminer@hotmail.com"
   sendEmail(emailTo, subject, bodyText, "/etc/hosts")

   print(EXENAME,EXEPATH,ping('google.com'))
   (returncode,out,err) = execCommand('ls -la')
   print("returncode = %d. stdout = %s. stderr = %s." % (returncode,out,err))

   try:
      print("Getting lock...")
      getLock("genutil")
      print("sleeping with lock...")
      time.sleep(5)
      print("Freeing lock...")
      freeLock()
   except GeneralError as e:
      print("getLock exception:", e)
   print("Done")


'''
Zuppa: a program to write Zotero item URIs into Zotero article PDF files

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2020 by Michael Hucka and the California Institute of Technology.
This code is open-source software released under a 3-clause BSD license.
Please see the file "LICENSE" for more information.
'''

from   bun import UI, inform, warn, alert, alert_fatal
from   commonpy.data_utils import timestamp
from   commonpy.interrupt import config_interrupt
from   boltons.debugutils import pdb_on_signal
import os
from   os import path, cpu_count
import plac
import signal
import sys
from   sys import exit as exit

if __debug__:
    from sidetrack import set_debug, log, logr

import zuppa
from zuppa import print_version
from .exceptions import *
from .exit_codes import ExitCode
from .main_body import MainBody
from .methods import methods_list

# .............................................................................

@plac.annotations(
    api_key    = ('API key to access the Zotero API service',                'option', 'a'),
    no_color   = ('do not color-code terminal output',                       'flag',   'C'),
    after_date = ('only act on files created or modified after date "D"',    'option', 'd'),
    identifier = ('Zotero user ID for API calls',                            'option', 'i'),
    no_keyring = ('do not store credentials in the keyring service',         'flag',   'K'),
    list       = ('print list of known methods',                             'flag',   'l'),
    methods    = ('select how the URIs are to be stored (default: link)',    'option', 'm'),
    dry_run    = ('report what would be done without actually doing it',     'flag',   'n'),
    quiet      = ('be less chatty -- only print important messages',         'flag',   'q'),
    version    = ('print version info and exit',                             'flag',   'V'),
    debug      = ('write detailed trace to "OUT" ("-" means console)',       'option', '@'),
    files      = 'file(s) and/or folder(s) containing Zotero article PDF files',
)

def main(api_key = 'A', no_color = False, after_date = 'D', identifier = 'I',
         no_keyring = False,  list = False, methods = 'M', dry_run = False,
         quiet = False, version = False, debug = 'OUT', *files):
    '''Zuppa ("Zotero URI PDF Property Annotator") is a tool for Zotero users.

Zuppa writes Zotero item URIs into the PDF files and/or the macOS Finder
comments of PDF files in the user's Zotero database. This makes it possible
to look up the Zotero entry of a PDF file from outside of Zotero.

Credentials for Zotero access
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Zuppa needs to know the user's personal library identifier (also known as the
"userID") and a Zotero API key. By default, it tries to get this information
from the user's keychain. If the values do not exist in the keychain from a
previous run, Zuppa will ask the user, and (unless the -K option is given)
store the values in the user's keychain so that it does not have to ask again
in the future. It is also possible to supply the identifier and API key on
the command line using the -i and -a options, respectively; the given values
will then override the values stored in the keychain (unless the -K option is
also given). This is also how you can replace previously-stored values: use
-i and -a (without -K) and the new values will override the stored values.

To find out your Zotero userID and create an API key, log in to your Zotero
account at Zotero.org and visit https://www.zotero.org/settings/keys

Basic usage
~~~~~~~~~~~

Zuppa can operate on a folder, or one or more individual PDF files, or a mix
of both. Suppose your local Zotero database is located in ~/my-zotero/. Perhaps
the simplest way to run Zuppa is the following command:

  zuppa ~/my-zotero

If this is your first run of Zuppa, it will ask you for your userID and API
key, then search for PDF files recursively under ~/my-zotero/.  For each PDF
file found, Zuppa will contact the Zotero servers over the network and
determine the item URI for the bibliographic entry containing that PDF
file. Finally, it will use the default method of writing the Zotero link,
which is to write it into the Finder comments for the PDF file.

Instead of a folder, you can invoke zuppa on one or more individual files (but
be careful to quote pathnames with spaces in them, such as in this example):

  zuppa "~/my-zotero/storage/26GS7CZL/Smith 2020 Paper.pdf"

Zuppa supports multiple methods of writing the Zotero select link. The default
is to write it into the Finder comments. The option -l will cause Zuppa to
print a list of all the methods available, then exit. The option -m can be
used to select one or more methods when running Zuppa. (Separate the method
names with commas, without spaces.) For example,

 zuppa -m findercomment,pdfsubject ~/my-zotero/storage

will make Zuppa write the Zotero select link into the Finder comments as well
as the PDF metadata attribute "Subject".

At this time, the following methods are available:

  findercomment: prepends the Zotero item URI to the Finder comments for
    the file. It tries to be careful: if it finds a Zotero URI as the first
    thing in the comments, it replaces that URI instead of prepending a new
    one. However, Finder comments are notorious for being easy to damage or
    lose, so beware that Zuppa may irretrievably corrupt any existing Finder
    comments on the file.

  pdfsubject: rewrites the Subject metadata field in the PDF file. This is
    not the same as the Title field; for some users, the Subject field is not
    used for any other purpose and thus can be usefully hijacked for the
    purpose of storing the Zotero item URI. This makes the value accessible
    from macOS Preview, Adobe Acrobat, DEVONthink, and presumably any other
    application that can read the PDF metadata fields.

  pdfproducer: rewrites the Producer metadata field in the PDF file. For
    some users, this field has not utility, and thus can be usefully hijacked
    for the purpose of storing the Zotero item URI. This makes the value
    accessible from macOS Preview, Adobe Acrobat, DEVONthink, and presumably
    any other application that can read the PDF metadata fields. However,
    note that some users (archivists, forensics investigators, possibly
    others) do use the Producer field, and overwriting it may be undesirable.

Filtering by date
~~~~~~~~~~~~~~~~~

If the -d option is given, the PDF files will be filtered to use only those
whose last-modified date/time stamp is no older than the given date/time
description. Valid descriptors are those accepted by the Python dateparser
library. Make sure to enclose descriptions within single or double
quotes. Examples:

 zuppa -d "2 weeks ago" ....
 zuppa -d "2014-08-29" ....
 zuppa -d "12 Dec 2014" ....
 zuppa -d "July 4, 2013" ....

Additional command-line arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To make Zuppa only print what it would do without actually doing it, use
the -n "dry run" option.

If given the -q option, Zuppa will not print its usual informational messages
while it is working. It will only print messages for warnings or errors.
By default messages printed by Zuppa are also color-coded. If given the
option -C, Zuppa will not color the text of messages it prints. (This latter
option is useful when running Zuppa within subshells inside other environments
such as Emacs.)

If given the -V option, this program will print the version and other
information, and exit without doing anything else.

If given the -@ argument, this program will output a detailed trace of what it
is doing. The debug trace will be sent to the given destination, which can
be '-' to indicate console output, or a file path to send the output to a file.

When -@ has been given, Zuppa also installs a signal handler on signal SIGUSR1
that will drop Zuppa into the pdb debugger if the signal is sent to the
running process.


Return values
~~~~~~~~~~~~~

This program exits with a return code of 0 if no problems are encountered.
It returns a nonzero value otherwise. The following table lists the possible
return values:

  0 = success -- program completed normally
  1 = the user interrupted the program's execution
  2 = encountered a bad or missing value for an option
  3 = no network detected -- cannot proceed
  4 = file error -- encountered a problem with a file
  5 = server error -- encountered a problem with a server
  6 = an exception or fatal error occurred

Command-line arguments summary
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

    # Set up debug logging as soon as possible, if requested ------------------

    if debug != 'OUT':
        if __debug__: set_debug(True, debug)
        import faulthandler
        faulthandler.enable()
        if not sys.platform.startswith('win'):
            # Even with a different signal, I can't get this to work on Win.
            pdb_on_signal(signal.SIGUSR1)

    # Preprocess arguments and handle early exits -----------------------------

    ui = UI('Zuppa', 'Zotero URI PDF Property Annotator',
            use_color = not no_color, be_quiet = quiet)
    ui.start()

    if version:
        print_version()
        exit(int(ExitCode.success))
    if list:
        inform('Known methods: [cyan2]{}[/]', ', '.join(methods_list()))
        exit(int(ExitCode.success))

    methods = ['findercomment'] if methods == 'M' else methods.lower().split(',')

    # Do the real work --------------------------------------------------------

    if __debug__: log('='*8 + f' started {timestamp()} ' + '='*8)
    body = exception = None
    try:
        body = MainBody(files       = files,
                        api_key     = None if api_key == 'A' else api_key,
                        user_id     = None if identifier == 'I' else identifier,
                        use_keyring = not no_keyring,
                        after_date  = None if after_date == 'D' else after_date,
                        methods     = methods,
                        dry_run     = dry_run)
        config_interrupt(body.stop, UserCancelled(ExitCode.user_interrupt))
        body.run()
        exception = body.exception
    except Exception as ex:
        exception = sys.exc_info()

    # Try to deal with exceptions gracefully ----------------------------------

    exit_code = ExitCode.success
    if exception:
        if __debug__: log(f'main body returned an exception: {exception}')
        if exception[0] == CannotProceed:
            exit_code = exception[1].args[0]
        elif exception[0] in [KeyboardInterrupt, UserCancelled]:
            warn('Interrupted.')
            exit_code = ExitCode.user_interrupt
        else:
            msg = str(exception[1])
            alert_fatal(f'Encountered error {exception[0].__name__}: {msg}')
            exit_code = ExitCode.exception
            if __debug__:
                from traceback import format_exception
                details = ''.join(format_exception(*exception))
                logr(f'Exception: {msg}\n{details}')
    else:
        inform('Done.')

    # And exit ----------------------------------------------------------------

    if __debug__: log('_'*8 + f' stopped {timestamp()} ' + '_'*8)
    if __debug__: log(f'exiting with exit code {exit_code}')
    exit(int(exit_code))


# Main entry point.
# .............................................................................

# The following entry point definition is for the console_scripts keyword
# option to setuptools.  The entry point for console_scripts has to be a
# function that takes zero arguments.
def console_scripts_main():
    plac.call(main)

# The following allows users to invoke this using "python3 -m handprint".
if __name__ == '__main__':
    plac.call(main)

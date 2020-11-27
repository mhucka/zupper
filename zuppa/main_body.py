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

from   bun import inform, warn, alert, alert_fatal
from   commonpy.data_utils import DATE_FORMAT, pluralized, timestamp, parsed_datetime
from   commonpy.file_utils import filename_extension, files_in_directory
from   commonpy.network_utils import net, network_available
from   datetime import datetime
import os
from   os import path
from   pathlib import Path
import shutil
import sys

if __debug__:
    from sidetrack import log

from .exceptions import *
from .exit_codes import ExitCode
from .methods import KNOWN_METHODS, methods_list
from .zotero import Zotero


# Exported classes.
# .............................................................................

class MainBody(object):
    '''Main body for Handprint.'''

    def __init__(self, **kwargs):
        '''Initialize internal state.'''

        # Assign parameters to self to make them available within this object.
        for key, value in kwargs.items():
            if __debug__: log(f'parameter value self.{key} = {value}')
            setattr(self, key, value)

        # We expose attribute "exception" that callers can use to find out
        # if the thread finished normally or with an exception.
        self.exception = None

        # Create and initialize objects for the URI writers we will use.
        self._writers = []
        for method_name in self.methods:
            method = KNOWN_METHODS[method_name]()
            self._writers.append(method)


    def run(self):
        '''Run the main body.'''

        if __debug__: log('running MainBody')
        try:
            self._do_preflight()
            self._do_main_work()
        except Exception as ex:
            if __debug__: log(f'exception in main body: {str(ex)}')
            self.exception = sys.exc_info()
        if __debug__: log('finished MainBody')


    def stop(self):
        '''Stop the main body.'''
        if __debug__: log('stopping ...')
        pass


    def _do_preflight(self):
        '''Check the option values given by the user, and do other prep.'''

        if not network_available():
            alert_fatal('No network connection.')
            raise CannotProceed(ExitCode.no_network)

        # Sanity-check the arguments ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        hint = f'(Hint: use -h for help.)'

        if not all(s in methods_list() for s in self.methods):
            alert_fatal(f'"{methods}" is/are not known methods. {hint}')
            exit(int(ExitCode.bad_arg))
        if not self.use_keyring and not any([self.api_key, self.user_id]):
            alert_fatal(f"Need Zotero credentials if not using keyring. {hint}")
            raise CannotProceed(ExitCode.bad_arg)
        if any(item.startswith('-') for item in self.files):
            alert_fatal(f'Unrecognized option in arguments. {hint}')
            raise CannotProceed(ExitCode.bad_arg)

        if self.after_date:
            try:
                # Convert user's input into a canonical format.
                self.after_date = parsed_datetime(self.after_date)
                self.after_date_str = self.after_date.strftime(DATE_FORMAT)
                if __debug__: log(f'parsed after_date as {self.after_date_str}')
            except Exception as ex:
                alert_fatal(f'Unable to parse after_date: "{str(ex)}". {hint}')
                raise CannotProceed(ExitCode.bad_arg)

        # Set up Zotero connection and gather files for work ~~~~~~~~~~~~~~~~~~

        self._zotero = Zotero(self.api_key, self.user_id, self.use_keyring)

        self._files = []
        if __debug__: log(f'gathering list of PDF files ...')
        for item in self.files:
            if path.isfile(item) and filename_extension(item) == '.pdf':
                self._files.append(item)
            elif path.isdir(item):
                if __debug__: log(f'adding PDF files in subdirectory {item}')
                self._files += files_in_directory(item, extensions = ['.pdf'])
            else:
                warn(f'Not a PDF file or folder of files: "{item}"')
        if __debug__: log(f'gathered {pluralized("PDF file", self._files, True)}')

        if self.after_date:
            if __debug__: log(f'filtering files by date {self.after_date_str}')
            kept = []
            tzinfo = self.after_date.tzinfo
            for pdffile in self.files:
                mtime = datetime.fromtimestamp(Path(pdffile).stat().st_mtime)
                if mtime.replace(tzinfo = tzinfo) >= self.after_date:
                    if __debug__: log(f'keeping {pdffile}')
                    kept.append(pdffile)
            self._files = kept

        if not self._files:
            alert_fatal('No PDF files to process; quitting.')
            raise CannotProceed(ExitCode.bad_arg)


    def _do_main_work(self):
        warn(f'Running in dry run mode – will not modify files.')
        inform(f'Will process {pluralized("PDF file", self._files, True)}'
               + f' using {pluralized("method", self.methods)}'
               + f' [cyan2]{", ".join(self.methods)}[/].')
        num_targets = len(self._files)

        for pdffile in self._files:
            record = self._zotero.record_for_file(pdffile)
            if __debug__: log(f'{record.parent_key} is parent of {record.key}'
                              + f' for file {pdffile}')
            for writer in self._writers:
                writer.write_uri(pdffile, record.link, self.dry_run)

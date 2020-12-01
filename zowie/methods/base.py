'''
base.py: base class definition for annotation methods in Zowie

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2020 by Michael Hucka and the California Institute of Technology.
This code is open-source software released under a 3-clause BSD license.
Please see the file "LICENSE" for more information.
'''

from abc import ABC, abstractmethod

if __debug__:
    from sidetrack import log


# Class definitions.
# .............................................................................
# Basics for the __eq__ etc. methods came from
# https://stackoverflow.com/questions/1061283/lt-instead-of-cmp

class WriterMethod(ABC):
    def __init__(self):
        pass


    def __str__(self):
        return self.name()


    def __repr__(self):
        return self.name()


    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return not self.name() < other.name() and not other.name() < self.name()


    def __ne__(self, other):
        return not __eq__(self, other)


    def __lt__(self, other):
        return self.name() < other.name()


    def __gt__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return other.name() < self.name()


    def __le__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return not other.name() < self.name()


    def __ge__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return not self.name() < other.name()


    @property
    @abstractmethod
    def name(self):
        '''Returns the canonical internal name for this method.'''
        pass


    @property
    @classmethod
    @abstractmethod
    def description(self):
        '''Returns a description what this method does.'''
        pass


    @abstractmethod
    def write_link(self, file, uri, dry_run, overwrite):
        '''Write the link into the file.'''
        pass
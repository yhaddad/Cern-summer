"""
A library with selection functions used to select bins for the minization.

Implemented via subclassing (to make hand-crafted representation strings possible).
"""

from professor.tools import log as logging
from professor.tools.decorators import virtualmethod

class SelectionFunction(object):
    def __str__(self):
        return "<%s>"%(self.__class__.__name__)

    @virtualmethod
    def __call__(self, std):
        """std must be a SingleTuneData."""
        return None


class VetoEmpty(SelectionFunction):
    """Return False if refbin's y value and error are 0.

    So only bins with non-zero y value and error in the refernce data are
    passed through.
    """
    def __call__(self, std):
        for binid in std.iterkeys():
            bp = std[binid]
            if bp.refbin.getVal() == 0 and bp.refbin.getErr() == 0:
                bp.veto = True

## Alias
OmitEmpty = VetoEmpty


class WeightObservable(SelectionFunction):
    def __init__(self, obsname, weight):
        self.__obsname = obsname
        self.__weight = weight

    def __str__(self):
        return "<%s '%s' with weight '%g'>" % \
            (self.__class__.__name__, self.__obsname, self.__weight)

    def __call__(self, std):
        for binid in std.iterkeys():
            obsname = binid.split(':')[0]
            if obsname == self.__obsname:
                bp = std[binid]
                logging.debug("Weighting bin '%s' with %e" % \
                                  (binid, self.__weight))
                bp.weight = self.__weight

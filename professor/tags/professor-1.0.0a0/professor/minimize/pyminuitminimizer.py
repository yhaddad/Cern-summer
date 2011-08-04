"""
Nice PyMinuit(2) interface to the Minuit minimizer now maintained as part of ROOT.
"""

from professor.tools import log as logging

from baseminimizer import BaseMinimizer
from result import MinimizationResult

# Be tolerant if we don't have PyMinuit and try PyMinuit2 instead.
# The PyMinuit documentation promises that the class interfaces are the
# same.
try:
    from minuit2 import Minuit2 as Minuit
    from minuit2 import MinuitError
    logging.debug("Using PyMinuit2 as interface.")
except ImportError:
    from minuit import Minuit, MinuitError
    logging.debug("Using PyMinuit as interface.")

# Unless we want to edit the pyMinuit source-code, we have to live with some
# kind of a hack for the GoF definition. Since pyMinuit initializes using
# func.co_argcount, so the variables of the function need to be hardcoded.
# pyMinuit doesn't accept arrays or list, it counts the number of parameters
# as 1 all the time. Also, def chi2(*args): fails because the co_argcount
# is 0 here. A first approach was to define a chi2 for a number of dimension
# like chi2(x) chi2(x,y) and so on and use an if-statement.
# So at least the definition is now dynamic: I produce a string first and
# have it executed afterwards :-(


class PyMinuitMinimizer(BaseMinimizer):
    printminuit = 0
    maxtries = 1
    useminos = False
    def initMinimization(self):
        # The following call isn't doing anything for the moment, might
        # change in the future.
        super(PyMinuitMinimizer, self).initMinimization()

        dim = self.gof.tunedata.numParams()

        if dim > 100:
            err = "Mapping of Professor parameter names to Minuit names fails with more than 100 parameters!"
            raise RuntimeError(err)

        # Unless we're using more than 100 parameters the parameter names in
        # the wrapper function will be in alphabetically order and we can
        # map them easily to PARJ... names.
        #
        # Parameters are named after _M_inuit _P_arameter.
        mpnames = ["MP%02i"%(i) for i in xrange(dim)]
        funcargs = ", ".join(mpnames)
        funcdef = "def hackGoFWrapper("
        funcdef += funcargs
        funcdef += "): "
        funcdef += "return self.goffunc(["
        funcdef += funcargs
        funcdef += "])"
        exec funcdef in locals()
        logging.debug("Built GoF wrapper from:\n  '%s'" % funcdef)

        self.__minuit = Minuit(hackGoFWrapper, strategy=2)

        ## Turn on Minuit's printing if log level is low enough
        if self.printminuit != 0:
            self.__minuit.printMode = self.printminuit

        ## Fix parameters and set start point
        for i, mpname in enumerate(mpnames):
            realname = self.gof.tunedata.scaler.getKeys()[i]
            self.__minuit.values[mpname] = self.getStartpoint()[i]
            if self.getFixedParameter(realname) is not None:
                self.__minuit.fixed[mpname] = True
                self.__minuit.values[mpname] = self.getFixedParameter(realname)
                msg = "Fixing minuit parameter %s (%s) to %e" % \
                    (mpname, realname, self.getFixedParameter(realname))
                logging.debug(msg)
            if self.getParameterLimits(realname) is not None:
                self.__minuit.limits[mpname] = self.getParameterLimits(realname)
                msg = "Limiting minuit parameter %s (%s) to %s" % \
                    (mpname, realname, str(self.getParameterLimits(realname)))
                logging.debug(msg)


    def minimize(self):
        # list of floats
        pvals = []
        # list of pairs of floats:
        # [ (low err, high err), ...]
        perrs = []

        # initialize Minuit
        #self.__minuit.strategy = 2

        logging.debug("Starting MINUIT with\n" +
                      "  fixed: %s\n" % self.__minuit.fixed +
                      "  values: %s\n" % self.__minuit.values +
                      "  limits: %s" % self.__minuit.limits)

        # Call the minimizer,
        tries = 0
        while True:
            tries += 1
            try:
                self.__minuit.migrad()
            except MinuitError, err:
                if tries < self.maxtries:
                    logging.error("MIGRAD call #%i failed with: %s" % (tries, err))
                    logging.info("Current parameter values: %s" % self.__minuit.values)
                    logging.error("Trying again...")
                else:
                    logging.error("Reached maximal numer of tries %i, but "
                                  "MIGRAD failed: Raising error!" % self.maxtries)
                    raise MinimiserError("MIGRAD failed: " + str(err))
            else:
                logging.info("MIGRAD succeeded after %i tries." % (tries))
                break

        if self.useminos:
            # call minos to estimate errors
            try:
                self.__minuit.minos()
            except MinuitError, err:
                raise MinimiserError("MINOS failed: " + err.message)

            logging.debug("Results with MINOS:")
            for minuitname in sorted(self.__minuit.parameters):
                pv = self.__minuit.values[minuitname]
                dp_low = -self.__minuit.merrors[(minuitname, -1.0)]
                dp_high = self.__minuit.merrors[(minuitname, 1.0)]

                pvals.append(pv)
                perrs.append((dp_low, dp_high))
                logging.debug("  %s = %g -%g +%g" % (minuitname, pv, dp_low, dp_high))
        else:
            logging.debug("Results with MIGRAD:")
            for minuitname in sorted(self.__minuit.parameters):
                pv = self.__minuit.values[minuitname]
                dp = self.__minuit.errors[minuitname]

                pvals.append(pv)
                perrs.append((dp, dp))

                logging.debug("  %s = %g -+%g"%(minuitname, pv, dp))

        mr = MinimizationResult.withScaler(self.__minuit.fval,
                                           self.gof.calcNdof(),
                                           self.gof.tunedata.scaler, pvals,
                                           errscaled=perrs,
                                           covariance=self.__minuit.covariance,
                                           spmethod=self.getStartpointMethod())

        for pname in self.getAllFixedParameters():
            mr.setFixedFlag(pname)
        if len(self.getLimitedParameters()):
            mr.setLimitUsedFlag()

        return mr

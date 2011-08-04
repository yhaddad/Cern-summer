import itertools
import numpy

from matplotlib.transforms import blended_transform_factory

from professor import interpolation, minimize, fitfunctions
#from professor.tools import planelineprojection as plp
from professor.tools import parameter
from professor.tools import log as logging

from stylegen import StyleGenerator


class LineScanPlotter(object):
    """Class for data and methods needed for line scan plots.

    This class provides
        - data retrieval from files (e.g. loading interpolation files)
        - data preparation for plotting
        - plotting into given matplotlib axes objects
    """
    # default style for plotting
    scanstyle = {"color":"r", "marker":"o", "linestyle" :""}
    # we're plotting top to bottom so thick->thin, etc...
    ipolstyle = StyleGenerator(color = itertools.cycle(["r", "k", "b", "g"]),
                               linestyle = itertools.repeat("solid"),
                               linewidth = itertools.cycle(
                                                    numpy.arange(2.0, 0.3, -0.6)))
    pointstyle = {"color":"g"}

    def __init__(self, dataproxy, weightman):
        """
        weightman  -- a WeightManager object
        dataproxy  -- a DataProxy object
        """
        self.weightman = weightman
        self.dataproxy = dataproxy
        self.scandat = dataproxy.getMCData('linescan')
        self.ndof = True


        # { ipol method (as string)
        #       => nr of runs
        #           => list of (run comb OR minim. result)}
        self._runcombs = {}
        self.numresults = 0

        # data for the scan line points
        # 1D numpy.ndarray with parameter point
        self._p0 = None
        self._p1 = None
        self._numveripoints = None
        # 1D numpy.ndarray with line parameters
        self._ptilde = None
        # 2D numpy.ndarray with line scan parameter points
        # indices = [p_tilde index, parameter index]
        self._veripoints = None

    def setEndpoints(self, a=None, b=None, numpoints=100):
        """Update the scan points for ipol evaluation.

        a and b must be dictionaries as returned by
        tools.parameter.readParameterFile() .

        3 combinations are accepeted:
        * a and b given: a and b must be paramter dictionaries.

        * a given and b is None: a must be a parameter range dictionary.

        * a and b are None:  endpoints are taken from the scan data
                (point with lowest/hightes PROF_TUNE_PARAM).

        Parameters
        ----------
        a,b : dict
            endpoints of the scan line. Must be parameter dictionaries as
            returned by tools.parameter.readParameterFile() .
        numpoints : int
            The number of points at which the GoF of the interpolations is
            calculated.
        """
        self.scandat.loadAllRuns(loadhistos=False)
        availruns = self.scandat.availableruns

        if a is None and b is None:
            r0 = availruns[0]
            r1 = availruns[0]
            for r in availruns:
                if (self.scandat.getScanParam(r) <
                        self.scandat.getScanParam(r0)):
                    r0 = r
                if (self.scandat.getScanParam(r) >
                        self.scandat.getScanParam(r1)):
                    r1 = r
            logging.info("Using scan runs '%s' and '%s' as start/end"
                 " runs." % (r0, r1))
            endpoints = {}
            p0 = self.scandat.getRunParams(r0)
            p1 = self.scandat.getRunParams(r1)
            for k in p0.keys():
                endpoints[k] = (p0[k], p1[k])
        elif b is None:
            endpoints = a
        else:
            endpoints = {}
            for k in a.keys():
                endpoints[k] = (a[k], b[k])
        logging.info("Using endpoints:\n%s" % (parameter.prettyPrintParameter(endpoints)))

        self._numveripoints = numpoints
        self._ptilde = numpy.linspace(0.0, 1.0,
                                      num=self._numveripoints,
                                      endpoint=True)
        # calculate the parameter points for scanning the interpolation
        p0 = numpy.zeros(len(endpoints))
        p1 = numpy.zeros(len(endpoints))
        for i, pname in enumerate(sorted(endpoints.keys())):
            p0[i] = endpoints[pname][0]
            p1[i] = endpoints[pname][1]
        self._veripoints = p0 + (p1 - p0)*self._ptilde[:,numpy.newaxis]
        self._p0 = p0
        self._p1 = p1

    def getDirection(self):
        """Get the direction unit vector of this scan line as dict."""
        n = self._p1 - self._p0
        n /= numpy.linalg.norm(n)
        d = {}
        pnames = sorted(self.scandat.getParameterNames())
        for i, name in enumerate(pnames):
            d[name] = n[i]
        return d

    def getLineLength(self):
        """The length of the scan line from start- to end-point."""
        return numpy.linalg.norm(self._p1 - self._p0)

    def getMCScanData(self, pname):
        """Return an ndarray of (parameter, GoF) pairs."""
        r = numpy.zeros((len(self.scandat.availableruns), 2))
        for i, scanrun in enumerate(sorted(self.scandat.availableruns)):
            if pname in ("LINESCAN", "PROF_SCAN_PARAM"):
                r[i,0] = self.scandat.getScanParam(scanrun)
            else:
                r[i,0] = self.scandat.getParam(scanrun)
            scantundat = self.dataproxy.getTuneData(withref=True, withmc='linescan', useobs=self.weightman.observables)
            scantundat.applyObservableWeightDict(self.weightman)

            gofdata = fitfunctions.SimpleMCChi2(scantundat, scanrun)

            logging.debug("Scanrun %s: chi2=%e ndof=%e" % (
                          scanrun, gofdata.calcChi2(), gofdata.calcNdof()))
            if self.ndof:
                r[i,1] = gofdata.calcGoF()
            else:
                r[i,1] = gofdata.calcChi2()
        return r

    def getIpolData(self, ipolmethod, runcomb, pname):
        """Return an ndarray of (parameter, GoF) pairs."""
        if self._numveripoints is None:
            raise RuntimeError("setEndpoints() must be called before"
                               " getIpolData() !")

        logging.debug("Calculation GoF data for param(%s) for runs %s" % (
                      pname, runcomb))
        r = numpy.zeros((self._numveripoints, 2))

        tundat = self.dataproxy.getTuneData(withref=True, useipol=ipolmethod,
                useruns=runcomb, useobs=self.weightman.observables)
        tundat.applyObservableWeightDict(self.weightman)

        if pname not in ("LINESCAN", "PROF_SCAN_PARAM"):
            paridx = tundat.scaler.getIndex(pname)

        gofdata = fitfunctions.SimpleIpolChi2(tundat)
        for i in xrange(self._numveripoints):
            if pname in ("LINESCAN", "PROF_SCAN_PARAM"):
                r[i,0] = self._ptilde[i]
            else:
                r[i,0] = self._veripoints[i,paridx]
            gofdata.setParams(self._veripoints[i], scaled=False)

            if self.ndof:
                r[i,1] = gofdata.calcGoF()
            else:
                r[i,1] = gofdata.calcChi2()
            logging.debug("ipolrun: chi2=%e ndof=%e" % (
                          gofdata.calcChi2(), gofdata.calcNdof()))
        return r

    def GoFAxisLabel(self):
        """Get the GoF axis label."""
        if self.ndof:
            return r"$\chi^2/N_\mathrm{df}$"
        else:
            return r"$\chi^2$"

    def ParAxisLabel(self, pname):
        """Get the parameter axis label."""
        if pname.upper() in ("PROF_SCAN_PARAM", "LINESCAN"):
            return r"$\tilde{p}$"
        else:
            return r"Parameter $\mathtt{" + pname + "}$"

    def getXLongXTrans(self, point):
        """Get the length longitudinal and perpendicular to the scan line
        relative to the length of the scan line.

        Parameters
        ----------
            point : numpy.ndarray
                The unscaled point, i.e. in "generator units".
        """
        # lambd = plp.getLambda(point, self._p0, self._p1)
        logging.trace("Ptilde calculation: p=%s, p0=%s, p1=%s => ptilde=%e" % (point, self._p0, self._p1, lambd))
        dot = numpy.dot
        norm = numpy.linalg.norm
        d = norm(self._p1 - self._p0)
        n = (self._p1-self._p0) / d
        # relative longitudinal length
        pLong = dot(point-self._p0, n)*n
        xLong = norm(pLong)/d
        # relative transversal length
        pTrans = point - self._p0 - pLong
        xTrans = norm(pTrans)/d
        logging.trace("Projected %s on %s => xL = %e  xT = %e" % (point, n, xLong, xTrans))
        logging.trace("Check: %e ?= %e = sqrt(xL^2 + xT^2)" % (norm(point-self._p0)/d, numpy.sqrt(xLong**2 + xTrans**2)))

        return xLong, xTrans

    def pTilde(self, point):
        return self.getXLongXTrans(point)[0]

    def cosTheta(self, point):
        """Calulate cos(theta) between vector [point-p0] and line.

        This is a measurement of the "off-lineliness" of the given point.

        point  -- the unscaled point as ndarray
        """
        # shortcut name
        dot = numpy.dot
        norm = numpy.linalg.norm
        d = self._p1 - self._p0
        a = point - self._p0
        return float(dot(a,d))/(norm(a)*norm(d))

    def getResultPTildes(self):
        """Array of the pTildes of the results' parameter predictions."""
        r = numpy.zeros(self.numresults)
        for i, mr in enumerate(self.results):
            r[i] = self.pTilde(mr.parunscaled)
        return r

    def results(self):
        """Return the MinimizationResults stored in self._runcombs."""
        r = []
        # little helper to check if an item is a MinimizationResult
        def isMR(rc):
            return type(rc) == minimize.result.MinimizationResult

        for subdict in self._runcombs.itervalues():
            for runcomblist in subdict.itervalues():
                r.extend(filter(isMR, runcomblist))
        return r
    results = property(results, doc="the available minimisation results")

    def addResult(self, result):
        """Add a MinimizationResult.

        It's interpolation method and run combination will be used for
        calculating GoF from interpolation.

        In addition it can be used for plotting a histogram with the
        location of the results (see getResultPTildes()).
        """
        method = result.ipolmethod
        numruns = len(result.runs)
        if not self._runcombs.has_key(method):
            self._runcombs[method] = {}
        if not self._runcombs[method].has_key(numruns):
            self._runcombs[method][numruns] = []
        self._runcombs[method][numruns].append(result)
        self.numresults += 1

    def hasResults(self):
        return (self.numresults > 0)

    def addRunComb(self, runs, method):
        """Add a run combination that will be used for interpolation for GoF
        calculation.

        runs  -- the list of used runs
        method  -- the interpolation method as string
        """
        numruns = len(runs)
        if not self._runcombs.has_key(method):
            logging.debug("Preparing _runcombs for [%s]" % (method))
            self._runcombs[method] = {}
        if not self._runcombs[method].has_key(numruns):
            logging.debug("Preparing _runcombs for [%s][%s]" % (
                            method, numruns))
            self._runcombs[method][numruns] = []
        self._runcombs[method][numruns].append(runs)
        logging.debug("_runcombs[%s][%s] contains %i elements now" % (
                        method, numruns,
                        len(self._runcombs[method][numruns])))

    def getIpolMethodFromResult(self, result):
        return interpolation.getInterpolationClass(result.ipolmethod, True)


    def getAllIpolData(self, pname):
        """Return all scan data created for the added results and run combs.

        The return value is a list that is sorted by the number of data sets:
            [ (label, [set1, set2, ... , setN])
              (label, [set1, set2, ... , setM])]    with M > N
        """
        r = []
        for method in self._runcombs.keys():
            for numruns in self._runcombs[method].keys():
                runcombs = self._runcombs[method][numruns]
                if len(runcombs) > 1:
                    label = r"%s polynomials, $N=%i$" % (
                            method, numruns)
                else:
                    label = r"%s polynomial, $N=%i$" % (
                            method, numruns)
                logging.info("Calculating ~%i interpolations for '%s'" % (
                             len(runcombs), label))
                i = 1

                pltdata = []
                plottedruncombs = []
                for runcomb in runcombs:
                    i += 1
                    if i%10 == 0:
                        logging.info("  Finished %4i/%i interpolations" % (
                                     i, len(runcombs)))
                    if type(runcomb) == minimize.result.MinimizationResult:
                        ipolmethod = self.getIpolMethodFromResult(runcomb)
                        runcomb = runcomb.runs
                    # only plot if necessary
                    if runcomb in plottedruncombs:
                        # logging.info("Already plotted runcomb %s" % (runcomb))
                        continue
                    # logging.info("Plotting for runcomb %s" % (runcomb))
                    plottedruncombs.append(runcomb)
                    #data = self.dataproxy.getTuneData(withref=True, useipol=self.getIpolMethodFromResult,
                            #useruns=runcomb,
                            #useobs=self.weightman.observables)
                    data = self.getIpolData(ipolmethod, runcomb, pname)
                    pltdata.append(data)
                r.append((label, pltdata))
                logging
        return sorted(r, key = lambda label_sets:len(label_sets[1]))

    def plotIpolScanData(self, axes, pname, z=5, style=None):
        """Plot ipol scan data top-to-bottom in axes.

        The highest zorder used plus 1 is returned.

        Ordering is done by the number of lines to plot.

        style  -- style can be either a generator (with a next() method,
                  e.g. a StyleGenerator instance) that returns a style dict
                  or a style dict. (optional)
        """

        if style is None:
            style = self.ipolstyle
        logging.debug("Plotting with style: %s" % (style))
        logging.debug("dir(style) => %s" %(dir(style)))

        logging.info("Calculating interpolation GoF data (this might take"
                     " some time!)")
        label_xys = self.getAllIpolData(pname)
        numipols = len(label_xys)
        z += numipols
        for i, (label, xys) in enumerate(label_xys):
            logging.info("Plotting interpolation line class %i/%i" % (i+1, numipols))
            if hasattr(style, "next"):
                thisstyle = style.next()
            else:
                thisstyle = style
            # TODO warn -> debug
            logging.debug("plotting %s with zorder=%i and style %s" % (
                label, z, thisstyle))
            axes.plot(xys[0][:,0], xys[0][:,1], label=label, zorder=z, **thisstyle)
            for xy in xys[1:]:
                axes.plot(xy[:,0], xy[:,1], label="_nolabel_", zorder=z, **thisstyle)
            z -= 1
        logging.debug("final z=%i" % (z))
        return z + len(label_xys) + 1

    def plotMCScanData(self, axes, pname, z=10, style=None):
        """
        style  -- a dict with plot() style kwargs (optional)
        """
        if style is None:
            style = self.scanstyle
        xy = self.getMCScanData(pname)
        axes.plot(xy[:,0], xy[:,1], label="scan MC data", zorder=z, **style)
        return z + 1

    def plotPoints(self, labeled_points, axes, pname, z=15, style=None, labelypos=0.1):
        """Plot the points with labes as vertical lines.

        TODO: bands

        For a line scan the projection on the line scan is plotted.

        labeled_points  -- a nested dict {label: { "pname1" :val, ...} }
        style  -- a dict with axvline() style kwargs (must contain "color")
                (optional)
        """
        if style is None:
            style = self.pointstyle
        # x in data coords and y in axes coords
        mytransform = blended_transform_factory(axes.transData, axes.transAxes)
        for label, point in labeled_points.items():
            if pname in ("LINESCAN", "PROF_SCAN_PARAM"):
                # convert parameter dict to ndarray
                p = numpy.zeros(len(point))
                for i, k in enumerate(sorted(point.keys())):
                    p[i] = point[k]
                x = self.pTilde(p)
                logging.info("Point '%s' has a cos(theta)=%e with the scan"
                             " line." % (label, self.cosTheta(p)))
            else:
                x = point[pname]
            logging.debug("Plotting vline %s at x=%e" % (label, x))
            axes.axvline(x, zorder=z, **style)
            # ORIG
            axes.text(x+0.01, labelypos, label, transform=mytransform,
                      rotation="vertical",
                      verticalalignment="bottom", horizontalalignment="left",
                      color=style["color"])
            # K5 steep
            # axes.text(x+0.01, 0.9, label, transform=mytransform,
                      # rotation="vertical",
                      # verticalalignment="top", horizontalalignment="left",
                      # color=style["color"])
            # K6 shallow
            # axes.text(x+0.01, 0.2, label, transform=mytransform,
                      # rotation="vertical",
                      # verticalalignment="bottom", horizontalalignment="left",
                      # color=style["color"])
        return z+1


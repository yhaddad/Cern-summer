"""
A mixed bag of functions for various tasks from statistical measures and
correlations, to sorting and clustering helpers.

TODO: Split this into more specific modules, e.g. prof.tools.sort, prof.tools.stats, etc.
"""

import numpy, scipy, re
from scipy import cluster, linalg, matrix

from professor.tools import log as logging


## Statistical formulas


def rms(alist):
    """
    Calculates the rms from a list.
    """
    if len(alist) > 1:
        return numpy.sqrt(sum([(i - numpy.mean(alist))**2
            for i in alist])/(len(alist)-1.))
    else:
       logging.warning("More than one item needed to calculate RMS, thus returning 0")
       return 0.


def weightedMean(tuplelist):
    """ tuplelist: [(x0, sigma x0), (x1, sigma x1), ...] """
    A = sum([value/sigma**2 for value, sigma in tuplelist])
    B = sum([1./sigma**2 for value, sigma in tuplelist])
    return A/B, 1./numpy.sqrt(B)


def gauss(x, mu=0, sigma=1):
    return 1./(numpy.sqrt(2*numpy.pi)*sigma) * numpy.exp(
            -(x-mu)**2/(2*sigma**2))


def noverk(n,k):
    """ calculate the binomial coefficent of n over k """
    return  scipy.factorial(n)/(scipy.factorial(k)*scipy.factorial(n-k))


def getCorrelation(covmat, par1, par2):
    """ this returns the correlation of two parameters using the covariance
        matrix
        covmat has to be a dictionary with keys as such: (par_i, par_j)
        e.g. as stored in MinimizationResult.covariance
    """
    return covmat[(par1, par2)]/(
            numpy.sqrt(covmat[(par1, par1)])*numpy.sqrt(covmat[(par2, par2)]))


def getCovMatFromSample(sample):
    """ sample is a dict {PARAM:[values...] ...} """
    covmat={}
    means = {}
    for k, v in sample.iteritems():
        means[k] = numpy.mean(v)
    def cov_xy(x,y):
        cov = 0
        for i in xrange(len(sample[x])):
            cov += (sample[x][i] - means[x])*(sample[y][i] - means[y])
        return cov/(len(sample[x]) - 1.)
    for x in sample.keys():
        for y in sample.keys():
            covmat[(x,y)] = cov_xy(x,y)
    return covmat


def convertCovMatToArray(covmat, names=None):
    """ This converts a dict-type correlation or covariance matrix
        into an array-type matrix, suitable for e.g. the eigenDecomposition.
    """

    if names is None:
        names = list(set(numpy.array(covmat.keys())[:,0]))
    else:
        if len(names) == int(numpy.sqrt(len(covmat.keys()))):
            pass
        else:
            raise ValueError("Number of names unequal to matrix dimension!")
    V = numpy.diag(numpy.zeros(len(names)))
    for m, x in enumerate(names):
        for n, y in enumerate(names):
            V[m][n] = covmat[(x,y)]
    return V, names


def convertCovMatToCorrMat(covmat):
    """ This converts the dict-type covariance matrix into a dict-type
        correlation matrix.
    """
    C = {}
    for k, v in covmat.iteritems():
        C[k] = getCorrelation(covmat, k[0], k[1])
    return C


def eigenDecomposition(mat):
    """ given, that M is a symmetric,real NxN matrix, an eigen decomposition is
        always possible, such that M can be written as
        M = T_transp * S * T   (orthogonal transformation)
        with T_transp * T = 1_N and S being a diagonal matrix with the
        eigenvalues of M on the diagonal.
        The return values are:\n
                T_transp, S, T
        T and T_trans are scipy matrices, S is a list of real eigenvalues
    """
    A = matrix(mat)
    #!scipy.linalg.eig returns the transposed matrix of eigenvectors
    eigenvalues, T_trans = linalg.eig(A)
    return (matrix(T_trans),
            map(float, map(numpy.real, eigenvalues)),
            matrix(T_trans).transpose())


def getExtremalDirection(covmat, direction='shallow'):
    """Calculate an extremal direction (of a MinimizationResult) based on a
    diagonalised covariance matrix.
    """
    T_transp, S, T = eigenDecomposition(covmat)
    #
    # create unit vector in the rotated system (where covmat is diagonal),
    # that points in the direction of the largest diagonalised covariance
    # matrix's element
    w = list(numpy.zeros(len(S)))
    S_abs = map(abs, S)
    # use most 'extreme' eigenvalue
    if direction=='shallow':
        ## use the, according to amount, largest eigenvalue
        w[S_abs.index(max(S_abs))] = 1.
    elif direction=='steep':
        ## use the, according to amount, smallest eigenvalue
        w[S_abs.index(min(S_abs))] = 1.
    else:
        raise ValueError("direction '%s' not supported, use 'shallow' or"
                         " 'steep'" % (direction))
    # rotate this vector back into the original system
    return T*(matrix(w).transpose())


def transformParameter(parameter, T_transp):
    """ this transforms a parameter into the space, where a certain
        covariance matrix is diagonal.
        parameter has to by a list
    """
    return T_transp * matrix(parameter).transpose()


## Helper function(s) for nicer sorting

def cmpByInt(sa, sb):
    """Compare two strings by numbers found in them.

    If one or both lack a number usual string-comparision is performed.

    Used to sort Pythia's PARJ(<NUM>) parameters.
    """
    pattern = re.compile(r'[0-9]+')
    try:
        numa = int(pattern.findall(sa)[0])
        numb = int(pattern.findall(sb)[0])
        return cmp(numa, numb)
    except IndexError:
        # failed to find a number
        return cmp(sa, sb)


## Cluster search
def checkForClustering(plist, K, param):
    a = numpy.array([[i] for i in plist])
    for i in xrange(1, len(plist) + 1):
        clusters, labels = cluster.vq.kmeans2(a,i)
        nrofcls = []
        for j in xrange(i):
            if not list(labels).count(j) == 0:
                nrofcls.append(list(labels).count(j))
        if len(nrofcls) == i:
            logging.info('At K=%i for param %s the results seem to cluster into %i regions' % (K, param, i))

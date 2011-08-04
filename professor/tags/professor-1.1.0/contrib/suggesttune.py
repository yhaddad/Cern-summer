#!/usr/bin/env python

USAGE = \
"""
"""

import sys
import os, re
import numpy
import pylab
from scipy import cluster

# Professor imports and config
from professor.tools.config import Config
from professor import rivetreader
from professor.minimize import result
from professor.tools import stats

conf = Config()
conf.setUsage(USAGE)

logger = conf.initModule("tuned",
        {"debug" : (False, conf.convBool, True,
                    "print debugging messages")
        ,"resultsdir": (".", str, True,
                    "specify directory in which to write out chi2 data files")
        ,"outdir": (".", str, True,
                    "specify directory in which to write out chi2 data files")
        ,"identifier": ('results', str, True,
                     " The XML results files to use ")
        ,"kbest": ('all', int, True,
                    " the K best chi2square yielding results will be used for "
                    " a tuning suggestion "
                    )
        ,"method": ('simplemean', str, True,
                    " the method used for the suggestion, either simple or "
                    " weighted mean "
                    )
        ,"plot": (False, conf.convBool, True,
                    " whether to use plot mmode or not "
                    )
        })

(opts, args) = conf.parseCommandline()

# turn debug logging on off
if conf.getOption('tuned', 'debug'):
    conf.setOption('global', 'loglevel', 'debug')
    DEBUG = True
    logger.info("running in debug mode")
else:
    conf.setOption('global', 'loglevel', 'info')
    DEBUG = False

def getTunPars(reslist, K):
    # extract the k best (in terms of chi2) tuningresults from reslist
    # to receive a list of ([unscaled-params] , according chi2) - pairs
    tunpars, tunchi2s = [], []
    for i in reslist.getKBest(K):
        tunpars.append(i.parunscaled)
        tunchi2s.append(i.chi2)
    return numpy.array(tunpars), numpy.array(tunchi2s)

def getClusteringOfFile(resfile):
    clusters = {}
    reslist = result.ResultList.fromXML(resfile)
    for param in reslist.getParamNames():
        print param, ':\n'
        clusters[param] = getLikelyClustering(reslist.getParamValues(param))
    return clusters

def checkForClustering(plist, K, param):
    a = numpy.array([[i] for i in plist])
    for i in xrange(1, len(plist) + 1):
        means, labels = validateClustering(plist, i)

def getSortedArray(array):
    return numpy.array(sorted(list(array)))

def getCluster(data,labels,i):
    """ return the dataelements that belong to the i-th cluster by parsing
        labels generated by cluster.vq.kmeans2
    """
    return [data[k] for k, lab in enumerate(labels) if lab ==i]

def getLikelyClustering(dataold, tries = 20):
    data = numpy.array([[i] for i in dataold])
    allsums = {}
    allclusters = {}
    #for i in xrange(1, len(data)+1):
    for i in xrange(1, 5):
        print 'attempting %i clusters:'%i
        for j in xrange(tries):
            s = validateClustering(data, i)
            if s is not False:
                #print '###########################\n', s
                sums = []
                for l in xrange(i):
                    #print 'probable cluster: ', getCluster(data, s[1],l)
                    #print 'cluster rms: ', stats.rms(getCluster(data, s[1],l))
                    cls = getCluster(data, s[1],l)
                    if not len(cls) < 2:
                        sums.append(stats.rms(getCluster(data, s[1],l)))
                    #print 'sum of rms: ', sum(sums)
            allsums[str(i)] = sum(sums)
            allclusters[str(i)] = s[1]
            break

    for k, v in allsums.iteritems():
        if v == min(allsums.values()):
            print 'it is very likely, that your data is clustered into %s clusters'%k
            return [getCluster(data, allclusters[k], i) for i in xrange(int(k))]

def validateClustering(data, k, maxloops = 1000):
    kmeanscluster = getSortedArray(cluster.vq.kmeans(numpy.array(data), k, thresh=1e-5)[0])
    match = False
    loops = 0
    while match is False:
        if loops > maxloops - 2:
            break
        means, labels = cluster.vq.kmeans2(numpy.array(data), k, thresh=1e-5)
        kmeans2cluster = getSortedArray(means)
        if (kmeans2cluster == kmeanscluster).all():
            match = True
        else:
            loops += 1
            continue
    bad = False
    if match:
        for i in xrange(k):
            if list(labels).count(i) == 0:
                print 'clustering failed!'
                bad = True
                break
    if not bad:
        return means, labels
    else:
        return False


# lookup xml-files in directory specified via resultsdir
resfiles = []
print opts.resultsdir
resfiles = [f for f in os.listdir(opts.resultsdir) if f.endswith('.xml') and
        f.startswith(opts.identifier)]

# create results-objects from all the files in resfiles
reslist = result.ResultList.fromXML(resfiles[0])
for i in resfiles[1:]:   # iterate over files
    reslist += result.ResultList.fromXML(i)

## check all results for clustering
#for param in reslist.getParamNames():
    #print param, ':\n'
    #getLikelyClustering(reslist.getParamValues(param), tries=100)

# make parameterwise histo of tune-results
for param in reslist.getParamNames():
    fig = pylab.figure(facecolor='w')
    sp = fig.add_subplot(1,1,1)
    #print 'tune results of param %s'%str(param)
    sp.set_title('tune results of param %s'%str(param))
    sp.hist(reslist.getParamValues(param), bins=int(numpy.floor(numpy.sqrt(len(reslist)))))
    sp.xaxis.set_label(param)
    sp.yaxis.set_label('Entries')
    fig.savefig(opts.outdir+'/resulsthisto_%s.eps'%param)









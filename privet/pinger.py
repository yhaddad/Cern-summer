#!/usr/bin/env python2

from commands import getstatusoutput
outputFile = open("lxplus.hosts", 'w')
for i in xrange(1,500):
    (stat, output) = getstatusoutput("ping lxplus" + str(i) + ".cern.ch -c 1")
    if output.find("unknown host") == -1:
        outputFile.write("mkawalec@lxplus" + str(i) + ".cern.ch 10"+ "\n")
        print i
outputFile.close()

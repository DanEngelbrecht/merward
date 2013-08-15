#!/usr/bin/python

import logging
import subprocess
import re
from sys import exit
import platform

# Could use "optimistic" branch checking...
# Only checkout branches affected by updated branches in fetch output

kUseHardcodedBranches = False
kUseHardcodedMissingMerges = False

kFeatureBranchPattern = re.compile('releases/[\d]+\.[\d]+\.x')
kHotpatchBranchPattern = re.compile('releases/[\d]+\.[\d]+\.[\d]+\.p.[\w]+')
kOnboardingBranchPattern = re.compile('onboarding/[\w]+')
kMasterBranchName = 'develop'

kFeatureTemplate = 'releases/{0}.{1}.x'
kHotpatchTemplate = 'releases/{0}.{1}.{2}.p.{3}'
kOnboardingTemplate = 'onboarding/{0}'

system = platform.system()

kGitexe = ''
kLoggingOutputFileName = ''

if system == 'Windows':
    kLoggingOutputFileName = 'C:\\tmp\\merward.log'
    kGitexe = 'C:\\Program Files (x86)\\Git\\bin\\git.exe'
elif system == 'Linux':
    kGitexe = '/usr/bin/git'
    kLoggingOutputFileName = '/home/dan/merward.log'

kObsoleteReleases = [kFeatureTemplate.format(1,1)]
#, kFeatureTemplate.format(2,0), kFeatureTemplate.format(2,1), kFeatureTemplate.format(2,2), kFeatureTemplate.format(2,3), kFeatureTemplate.format(2,4), kFeatureTemplate.format(2,5), kFeatureTemplate.format(2,6), kFeatureTemplate.format(2,7)]

def getHardcodedBranches():
    features = [kFeatureTemplate.format(2,11), kFeatureTemplate.format(2,12), kFeatureTemplate.format(2,13)]
    hotpatches = [kHotpatchTemplate.format(2,11,1,'OneCustomer'), kHotpatchTemplate.format(2,11,2,'OtherCustomer'), kHotpatchTemplate.format(2,13,7,'OtherCustomer')]
    onboardings = [kOnboardingTemplate.format('OtherCustomer')]
    return features, hotpatches, onboardings

def getHardcodedMissingMerges():
    missingMerges = dict()
    missingMerges[features[0]] = [hotpatches[0], hotpatches[1]]
    missingMerges[features[2]] = [hotpatches[2]]
    missingMerges[kMasterBranchName] = [onboardings[0]]
    return missingMerges
    


def cmd(args):
    try:
        logging.info('Executing: ' + str(args))
        output = subprocess.check_output(args, stderr=subprocess.STDOUT)
        logging.info('= ' + output)
        return output
    except subprocess.CalledProcessError as e:
        output = e.output
        logging.info('! ' + output)
        return output

def getFeatureParents(releasename, releases):
    parents = list()
    
    _, version = releasename.split('/')
    major,minor,_ = version.split('.')
    
    majorNum = int(major)
    minorNum = int(minor)

    nextMinor = minorNum + 1
    nextMajor = majorNum + 1
    
    nextMinorFeature = kFeatureTemplate.format(majorNum, nextMinor) 
    nextMajorFeature = kFeatureTemplate.format(nextMajor, 0) 
    
    minorExists = nextMinorFeature in releases 
    majorExists = nextMajorFeature in releases 
    
    while minorExists or majorExists:
        if minorExists:
            parents.append(nextMinorFeature)
            nextMinor = nextMinor + 1
            nextMinorFeature = kFeatureTemplate.format(majorNum, nextMinor) 
            minorExists = nextMinorFeature in releases 
        else:
            parents.append(nextMajorFeature)
            majorNum = nextMajor
            nextMinor = 1
            nextMajor = nextMajor + 1
            nextMinorFeature = kFeatureTemplate.format(majorNum, nextMinor) 
            nextMajorFeature = kFeatureTemplate.format(nextMajor, 0) 
            minorExists = nextMinorFeature in releases 
            majorExists = nextMajorFeature in releases 

    if kMasterBranchName in releases:
        parents.append(kMasterBranchName)

    return parents;

def getHotpatchParents(releasename, releases):
    parents = list()
    
    _, version = releasename.split('/')
    major,minor, _, _, _ = version.split('.')
    
    parentName = kFeatureTemplate.format(major, minor)
    
    if parentName in releases:
        parents.append(parentName)
        parents = parents + getFeatureParents(parentName, releases)
        
    return parents

def getOnboardingParents(releasename, releases):
    parents = list()
    
    if kMasterBranchName in releases:
        parents.append(kMasterBranchName)

    return parents;

def addRequirement(offerer, requirers, backwardsMap):
    if requirers:
        requierer = requirers[0]
        if requierer in backwardsMap:
            if offerer not in backwardsMap[requierer]:
                backwardsMap[requierer].append(offerer)
        else:
            backwardsMap[requierer] = [offerer]

def isOnboardingBranch(branchName):
    if re.match(kOnboardingBranchPattern, branchName):
        return True
    else:
        return False

def isHotpatchBranch(branchName):
    if re.match(kHotpatchBranchPattern, branchName):
        return True
    else:
        return False

def isFeatureBranch(branchName):
    if re.match(kFeatureBranchPattern, branchName):
        return True
    else:
        return False
    
def isDevelopBranch(branchName):
    return branchName == kMasterBranchName 

def getVersionNumber(branchName):
    if isDevelopBranch(branchName):
        return 0xfffffffff
    elif isOnboardingBranch(branchName):
        return 0xfff000000
    elif isFeatureBranch(branchName):
        _, version = branchName.split('/')
        major, minor, _ = version.split('.')
        majorNum = int(major)
        minorNum = int(minor)
        return (majorNum << 24) + (minorNum << 12) + 0xfff
    elif isHotpatchBranch(branchName):
        _, version = branchName.split('/')
        major, minor, patch, _, _ = version.split('.')
        majorNum = int(major)
        minorNum = int(minor)
        patchNum = int(patch)
        return (majorNum << 24) + (minorNum << 12) + patchNum
    else:
        return 0x000000000 

def versionCompare(x ,y):
    xVersion = getVersionNumber(x)
    yVersion = getVersionNumber(y)
    if xVersion < yVersion:
        return -1
    elif xVersion == yVersion:
        if x < y:
            return -1
        elif x == y:
            return 0
        else:
            return 1
    else:
        return 1

def getAllBranches(useHardcodedBranches):
    if useHardcodedBranches:
        return getHardcodedBranches()
    
    cmd([kGitexe, "fetch", "--all"])
    
    allbranchesoutput = cmd([kGitexe, "branch", "-r"])

    features = set()
    hotpatches = set()
    onboardings = set()

    logging.info('Skipping obsolete branches:\n' + str(kObsoleteReleases) + '\n')
    
    iterator = kFeatureBranchPattern.finditer(allbranchesoutput)
    for match in iterator:
        releasename = match.group()
        if releasename not in kObsoleteReleases:
            features.add(releasename)
    
    iterator = kHotpatchBranchPattern.finditer(allbranchesoutput)
    for match in iterator:
        releasename = match.group()
        if releasename not in kObsoleteReleases:
            hotpatches.add(releasename)
    
    iterator = kOnboardingBranchPattern.finditer(allbranchesoutput)
    for match in iterator:
        releasename = match.group()
        if releasename not in kObsoleteReleases:
            onboardings.add(releasename)
    
    return features, hotpatches, onboardings

def getBranchMapping(releases, features, hotpatches, onboardings):
    forwardMap = dict()
    backwardsMap = dict()
    
    for f in features:
        parentPath = getFeatureParents(f, releases)
        addRequirement(f, parentPath, backwardsMap)
        forwardMap[f] = parentPath
    
    for h in hotpatches:
        parentPath = getHotpatchParents(h, releases)
        addRequirement(h, parentPath, backwardsMap)
        forwardMap[h] = parentPath
    
    for o in onboardings:
        parentPath = getOnboardingParents(o, releases)
        addRequirement(o, parentPath, backwardsMap)
        forwardMap[o] = parentPath

    return forwardMap, backwardsMap

def logSortedBranchSet(title, branches):
    logging.info(title + ' branches:') 
    sortedBranches = list(branches)
    sortedBranches = sorted(sortedBranches, versionCompare)
    for f in sortedBranches:
        logging.info(f)
    
def calculateMissingMerges(useHardcodedMissingMerges, releases, backwardsMap):

    if useHardcodedMissingMerges:
        return getHardcodedMissingMerges()

    missingMerges = dict()
    
    releaseCount = len(releases)
    releaseIndex = 0
    
    for r in releases:
        print "Checking (" + str((100 * releaseIndex) / releaseCount) + "%): " + r
        releaseIndex = releaseIndex + 1
        logging.info("Checking out: " + r)
        cmd([kGitexe, "checkout", "-f", r])
    
        logging.info("Resetting: " + r)
        cmd([kGitexe, 'reset', '--hard', 'origin/'+r])
        if r in backwardsMap:
            unmergedOutput = cmd([kGitexe, 'branch', '--no-merged'])
            missing = []
            for require in sorted(backwardsMap[r], versionCompare):
                if require in unmergedOutput:
                    missing.append(require)
            if missing:
                logging.info("Missing merges for " + r + ":\n" + str(missing))
                missingMerges[r] = missing
            else:
                logging.info("No missing merges for " + r)
        else:
            logging.info("No merge requirements for " + r)
        logging.info('')
        
    return missingMerges

def buildMergeMap(missingMerges, forwardMap):
    mergeMap = {}
    for m in missingMerges:
        mergeMap[m] = set(missingMerges[m])
        if m in forwardMap:
            forwardMerges = forwardMap[m]
            s = m 
            for f in forwardMerges:
                if f in mergeMap:
                    mergeMap[f].add(s)
                else:
                    mergeMap[f] = {s}
                s = f
    return mergeMap

def outputOutputCmdSequence(mergeMap):
    mergeOrder = sorted(list(mergeMap.keys()), versionCompare)

    print "Make up to date with: "
    print "----------------------"
    
    for b in mergeOrder:
        print "git checkout -f " + b
        for m in sorted(list(mergeMap[b]), versionCompare):
            print "git merge " + m
        print "git push origin " +b

    print "----------------------"



########################################################################

logging.basicConfig(filename=kLoggingOutputFileName,level=logging.DEBUG)

features = set()
hotpatches = set()
onboardings = set()

features, hotpatches, onboardings = getAllBranches(kUseHardcodedBranches)

releases = []
releases.append(kMasterBranchName)
releases.extend(features.__iter__())
releases.extend(hotpatches.__iter__())
releases.extend(onboardings.__iter__())

forwardMap, backwardsMap = getBranchMapping(releases, features, hotpatches, onboardings)
    
missingMerges = dict()

releases = sorted(releases, versionCompare)

logging.info('Releases:') 
for r in releases:
    logging.info(r)
logging.info('\n') 

logSortedBranchSet('Feature' ,features)
logSortedBranchSet('Hotpatch', hotpatches)
logSortedBranchSet('Onboarding', onboardings)

logging.info('Forwards:')
for r in forwardMap:
    logging.info(r + ' -> ' + str(sorted(forwardMap[r], versionCompare)))
logging.info('\n') 

logging.info('Requires:')
for r in backwardsMap:
    logging.info(r + ' <- ' + str(sorted(backwardsMap[r], versionCompare)))
logging.info('\n') 

missingMerges = calculateMissingMerges(kUseHardcodedMissingMerges, releases, backwardsMap)

if missingMerges:
    print "Checking (100%): Missing merges:"
    for r in releases:
        if r in missingMerges:
            print "    " + r + ': ' + str(missingMerges[r])

    print

    mergeMap = buildMergeMap(missingMerges, forwardMap)
    outputOutputCmdSequence(mergeMap)
    
    exit(1)
else:
    print "Checking (100%)"
    exit(0)

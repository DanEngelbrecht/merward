#!/usr/bin/python

import logging
import subprocess
import re

featureBranchPattern = re.compile('releases/[\d]+\.[\d]+\.x')
hotpatchBranchPattern = re.compile('releases/[\d]+\.[\d]+\.[\d]+\.p.[\w]+')
onboardingBranchPattern = re.compile('onboarding/[\w]+')

gitexe = 'C:\\Program Files (x86)\\Git\\bin\\git.exe'

obsoleteReleases = ['releases/1.1.x', 'releases/2.0.x', 'releases/2.1.x', 'releases/2.2.x', 'releases/2.3.x', 'releases/2.4.x', 'releases/2.5.x', 'releases/2.6.x', 'releases/2.7.x']

featureTemplate = 'releases/{0}.{1}.x'

masterBranchName = 'develop'


def cmd(args):
    try:
        logging.info('Executing: ' + str(args))
        output = subprocess.check_output(args, stderr=subprocess.STDOUT, shell=True)
        logging.info('= ' + output)
        return output
    except subprocess.CalledProcessError as e:
        output = e.output
        logging.info('! ' + output)
        return output

def getFeatureParents(releasename, releases):
    parents = list()
    
    prefix, version = releasename.split('/')
    major,minor,x = version.split('.')
    
    majorNum = int(major)
    minorNum = int(minor)

    nextMinor = minorNum + 1
    nextMajor = majorNum + 1
    
    nextMinorFeature = featureTemplate.format(majorNum, nextMinor) 
    nextMajorFeature = featureTemplate.format(nextMajor, 0) 
    
    minorExists = nextMinorFeature in releases 
    majorExists = nextMajorFeature in releases 
    
    while minorExists or majorExists:
        if minorExists:
            parents.append(nextMinorFeature)
            nextMinor = nextMinor + 1
            nextMinorFeature = featureTemplate.format(majorNum, nextMinor) 
            minorExists = nextMinorFeature in releases 
        else:
            parents.append(nextMajorFeature)
            majorNum = nextMajor
            nextMinor = 1
            nextMajor = nextMajor + 1
            nextMinorFeature = featureTemplate.format(majorNum, nextMinor) 
            nextMajorFeature = featureTemplate.format(nextMajor, 0) 
            minorExists = nextMinorFeature in releases 
            majorExists = nextMajorFeature in releases 

    if masterBranchName in releases:
        parents.append(masterBranchName)

    return parents;

def getHotpatchParents(releasename, releases):
    parents = list()
    
    prefix, version = releasename.split('/')
    major,minor,patch,p,customer = version.split('.')
    
    parentName = featureTemplate.format(major, minor)
    
    if parentName in releases:
        parents.append(parentName)
        parents = parents + getFeatureParents(parentName, releases)
        
    return parents

def getOnboardingParents(releasename, releases):
    parents = list()
    
    if masterBranchName in releases:
        parents.append(masterBranchName)

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
    if re.match(onboardingBranchPattern, branchName):
        return True
    else:
        return False

def isHotpatchBranch(branchName):
    if re.match(hotpatchBranchPattern, branchName):
        return True
    else:
        return False

def isFeatureBranch(branchName):
    if re.match(featureBranchPattern, branchName):
        return True
    else:
        return False
    
def isDevelopBranch(branchName):
    return branchName == masterBranchName 

def getVersionNumber(branchName):
    if isDevelopBranch(branchName):
        return 0xfffffffff
    elif isOnboardingBranch(branchName):
        return 0xfff000000
    elif isFeatureBranch(branchName):
        prefix, version = branchName.split('/')
        major,minor,rest = version.split('.')
        majorNum = int(major)
        minorNum = int(minor)
        return (majorNum << 24) + (minorNum << 12) + 0xfff
    elif isHotpatchBranch(branchName):
        prefix, version = branchName.split('/')
        major,minor,patch,p,customer = version.split('.')
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


logging.basicConfig(filename='C:\\tmp\\merward.log',level=logging.DEBUG)

fetchoutput = cmd([gitexe, "fetch", "--all"])

allbranchesoutput = cmd([gitexe, "branch", "-r"])

releases = []

features = set()
hotpatches = set()
onboardings = set()

if masterBranchName in allbranchesoutput:
    releases.append(masterBranchName)

logging.info('Skipping obsolete branches:\n' + str(obsoleteReleases) + '\n')

iterator = featureBranchPattern.finditer(allbranchesoutput)
for match in iterator:
    releasename = match.group()
    if releasename not in obsoleteReleases:
        features.add(releasename)

iterator = hotpatchBranchPattern.finditer(allbranchesoutput)
for match in iterator:
    releasename = match.group()
    if releasename not in obsoleteReleases:
        hotpatches.add(releasename)

iterator = onboardingBranchPattern.finditer(allbranchesoutput)
for match in iterator:
    releasename = match.group()
    if releasename not in obsoleteReleases:
        onboardings.add(releasename)

releases.extend(features.__iter__())
releases.extend(hotpatches.__iter__())
releases.extend(onboardings.__iter__())

releases = sorted(releases, versionCompare)

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
    

logging.info('Releases:') 
for r in releases:
    logging.info(r)
logging.info('\n') 

logging.info('Feature branches:') 
sortedFeatures = list(features)
sortedFeatures = sorted(sortedFeatures, versionCompare)
for f in sortedFeatures:
    logging.info(f)
logging.info('\n') 

logging.info('Hotpatch branches:')
sortedHotpatches = list(hotpatches)
sortedHotpatches = sorted(sortedHotpatches, versionCompare)
for h in sortedHotpatches:
    logging.info(h)
logging.info('\n') 

logging.info('Onboarding branches:')
sortedOnboardings = list(onboardings)
sortedOnboardings = sorted(sortedOnboardings, versionCompare)
for o in sortedOnboardings:
    logging.info(o)
logging.info('\n') 

logging.info('Forwards:')
for r in forwardMap:
    logging.info(r + ' -> ' + str(sorted(forwardMap[r], versionCompare)))
logging.info('\n') 

logging.info('Requires:')
for r in backwardsMap:
    logging.info(r + ' <- ' + str(sorted(backwardsMap[r], versionCompare)))
logging.info('\n') 

for r in releases:
    logging.info("Checking out: " + r)
    cmd([gitexe, "checkout", "-f", r])

    logging.info("Resetting: " + r)
    cmd([gitexe, 'reset', '--hard', 'origin/'+r])
    if r in backwardsMap:
        unmergedOutput = cmd([gitexe, 'branch', '--no-merged'])
        missing = []
        for require in sorted(backwardsMap[r], versionCompare):
            if require in unmergedOutput:
                missing.append(require)
        if missing:
            logging.info("Missing merges for " + r + ":\n" + str(missing))
            print r + ": " + str(missing)
        else:
            logging.info("No missing merges for " + r)
    else:
        logging.info("No merge requirements for " + r)
    logging.info('')

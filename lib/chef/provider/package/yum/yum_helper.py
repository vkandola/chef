#!/usr/bin/env python3
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import sys
import yum
import signal
import os
import json
import re
from rpmUtils.miscutils import stringToVersion,compareEVR
from rpmUtils.arch import getBaseArch

base = None

def get_base():
    global base
    if base is None:
        base = yum.YumBase()
        base.preconf.debuglevel = -5
        base.preconf.errorlevel = -1
        base.preconf.plugins = True
    return base

def versioncompare(versions):
    if (versions[0] is None) or (versions[1] is None):
        outpipe.write('0\n')
        outpipe.flush()
    else:
        (e1, v1, r1) = stringToVersion(versions[0])
        (e2, v2, r2) = stringToVersion(versions[1])
        evr_comparison = compareEVR((e1, v1, r1), (e2, v2, r2))
        outpipe.write('{}\n'.format(evr_comparison))
        outpipe.flush()

def query(command):
    base = get_base()

    args = { 'name': command['provides'] }
    do_nevra = False
    if 'epoch' in command:
        args['epoch'] = command['epoch']
        do_nevra = True
    if 'version' in command:
        args['ver'] = command['version']
        do_nevra = True
    if 'release' in command:
        args['rel'] = command['release']
        do_nevra = True
    if 'arch' in command:
        desired_arch = command['arch']
        args['arch'] = command['arch']
        do_nevra = True
    else:
        desired_arch = getBaseArch()

    obj = None
    if command['action'] == "whatinstalled":
        obj = base.rpmdb
    else:
        obj = base.pkgSack

    if any(elem in command['provides'] for elem in r"<=>"):
        # if provides has '<', '=', or '>'
        pkgs = obj.searchProvides(command['provides'])
    elif do_nevra:
        pkgs = obj.searchNevra(**args)
    else:
        pats = [command['provides']]
        pkgs = obj.returnPackages(patterns=pats)

    if not pkgs:
        outpipe.write('{} nil nil\n'.format(command['provides'].split().pop(0)))
        outpipe.flush()
    else:
        # make sure we picked the package with the highest version
        pkgs = base.bestPackagesFromList(pkgs,arch=desired_arch,single_name=True)
        pkg = pkgs.pop(0)
        sys.stdout.write(str(pkg))
        outpipe.write('{} {}:{}-{} {}\n'.format(pkg.name, pkg.epoch, pkg.version, pkg.release, pkg.arch))
        outpipe.flush()

# the design of this helper is that it should try to be 'brittle' and fail hard and exit in order
# to keep process tables clean.  additional error handling should probably be added to the retry loop
# on the ruby side.
def exit_handler(signal, frame):
    sys.exit(0)

signal.signal(signal.SIGINT, exit_handler)
signal.signal(signal.SIGHUP, exit_handler)
signal.signal(signal.SIGPIPE, exit_handler)

if len(sys.argv) < 3:
  inpipe = sys.stdin
  outpipe = sys.stdout
else:
  inpipe = os.fdopen(int(sys.argv[1]), "r")
  outpipe = os.fdopen(int(sys.argv[2]), "w")

while 1:
    # kill self if we get orphaned (tragic)
    ppid = os.getppid()
    if ppid == 1:
        sys.exit(0)
    line = inpipe.readline()
    command = json.loads(line)
    if command['action'] == "whatinstalled":
        query(command)
    elif command['action'] == "whatavailable":
        query(command)
    elif command['action'] == "versioncompare":
        versioncompare(command['versions'])
    else:
        raise RuntimeError("bad command")

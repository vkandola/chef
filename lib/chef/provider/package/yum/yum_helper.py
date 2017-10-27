#!/usr/bin/env python3
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import sys
import yum
import hawkey
import signal
import os
import json

base = None

def get_base():
    global base
    if base is None:
      base = yum.YumBase()
      base.preconf.debuglevel = 0
      base.preconf.errorlevel = 0
      base.preconf.plugins = True
    return base

# FIXME: leaks memory and does not work
def flushcache():
    try:
        os.remove('/var/cache/yum/@System.solv')
    except OSError:
        pass
    get_sack().load_system_repo(build_cache=True)

def versioncompare(versions):
    sack = get_sack()
    if (versions[0] is None) or (versions[1] is None):
      sys.stdout.write('0\n')
    else:
      evr_comparison = sack.evr_cmp(versions[0], versions[1])
      sys.stdout.write('{}\n'.format(evr_comparison))

def query(command):
    base = get_base()

    matches = base.rpmdb.matchPackageNames([command['provides']])
    sys.stdout.write('TEST {}\n'.format(command['provides']))
    sys.stdout.write('TEST {}\n'.format(matches))
    sys.stdout.write('TEST {}\n'.format(base.returnPackagesByDep(command['provides'])))

    q = subj.get_best_query(sack, with_provides=True)

    if command['action'] == "whatinstalled":
        q = q.installed()

    if command['action'] == "whatavailable":
        q = q.available()

    if 'epoch' in command:
        q = q.filterm(epoch=int(command['epoch']))
    if 'version' in command:
        q = q.filterm(version__glob=command['version'])
    if 'release' in command:
        q = q.filterm(release__glob=command['release'])

    if 'arch' in command:
        q = q.filterm(arch__glob=command['arch'])

    # only apply the default arch query filter if it returns something
    archq = q.filter(arch=[ 'noarch', hawkey.detect_arch() ])
    if len(archq.run()) > 0:
        q = archq

    pkgs = q.latest(1).run()

    if not pkgs:
        sys.stdout.write('{} nil nil\n'.format(command['provides'].split().pop(0)))
    else:
        # make sure we picked the package with the highest version
        pkgs.sort
        pkg = pkgs.pop()
        sys.stdout.write('{} {}:{}-{} {}\n'.format(pkg.name, pkg.epoch, pkg.version, pkg.release, pkg.arch))

# the design of this helper is that it should try to be 'brittle' and fail hard and exit in order
# to keep process tables clean.  additional error handling should probably be added to the retry loop
# on the ruby side.
def exit_handler(signal, frame):
    sys.exit(0)

signal.signal(signal.SIGINT, exit_handler)
signal.signal(signal.SIGHUP, exit_handler)
signal.signal(signal.SIGPIPE, exit_handler)

while 1:
    # kill self if we get orphaned (tragic)
    ppid = os.getppid()
    if ppid == 1:
        sys.exit(0)
    line = sys.stdin.readline()
    command = json.loads(line)
    if command['action'] == "whatinstalled":
        query(command)
    elif command['action'] == "whatavailable":
        query(command)
    elif command['action'] == "flushcache":
        flushcache()
    elif command['action'] == "versioncompare":
        versioncompare(command['versions'])
    else:
        raise RuntimeError("bad command")

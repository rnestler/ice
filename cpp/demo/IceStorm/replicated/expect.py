#!/usr/bin/env python
# **********************************************************************
#
# Copyright (c) 2003-2007 ZeroC, Inc. All rights reserved.
#
# This copy of Ice is licensed to you under the terms described in the
# ICE_LICENSE file included in this distribution.
#
# **********************************************************************

import sys, os

try:
    import demoscript
except ImportError:
    for toplevel in [".", "..", "../..", "../../..", "../../../.."]:
        toplevel = os.path.normpath(toplevel)
        if os.path.exists(os.path.join(toplevel, "demoscript")):
            break
    else:
        raise "can't find toplevel directory!"
    sys.path.append(os.path.join(toplevel))
    import demoscript

import demoscript.Util
demoscript.Util.defaultLanguage = "C++"
import time, signal

desc = 'application.xml'
if demoscript.Util.mode == 'debug':
    fi = open(desc, "r")
    desc = 'tmp_application.xml'
    fo = open(desc, "w")
    for l in fi:
        if l.find('exe="icebox"'):
            l = l.replace('exe="icebox"', 'exe="iceboxd.exe"')
        fo.write(l)
    fi.close()
    fo.close()

print "cleaning databases...",
sys.stdout.flush()
demoscript.Util.cleanDbDir("db/node")
demoscript.Util.cleanDbDir("db/registry")
print "ok"

if demoscript.Util.defaultHost:
    args = ' --IceGrid.Node.PropertiesOverride="Ice.Default.Host=127.0.0.1"'
else:
    args = ''

print "starting icegridnode...",
sys.stdout.flush()
node = demoscript.Util.spawn('icegridnode --Ice.Config=config.grid --Ice.PrintAdapterReady %s' % (args))
node.expect('IceGrid.Registry.Internal ready\r{1,2}\nIceGrid.Registry.Server ready\r{1,2}\nIceGrid.Registry.Client ready\r{1,2}\nIceGrid.Node ready')
print "ok"

print "deploying application...",
sys.stdout.flush()
admin = demoscript.Util.spawn('icegridadmin --Ice.Config=config.grid')
admin.expect('>>>')
admin.sendline("application add \'%s\'" %(desc))
admin.expect('>>>')
print "ok"

print "testing pub/sub...",
sys.stdout.flush()
sub = demoscript.Util.spawn('./subscriber --Ice.PrintAdapterReady')
sub.expect('.* ready')

node.expect('Subscribe:.*Subscribe:.*Subscribe:')

pub = demoscript.Util.spawn('./publisher')

time.sleep(3)
sub.expect('[0-9][0-9]/[0-9][0-9].*\r{1,2}\n[0-9][0-9]/[0-9][0-9]')
print "ok"

print "testing replication...",
sys.stdout.flush()
# Start killing off the servers
admin.sendline('server disable DemoIceStorm-1')
admin.expect('>>>')
admin.sendline('server stop DemoIceStorm-1')
admin.expect('>>>')

time.sleep(3)
sub.expect('[0-9][0-9]/[0-9][0-9].*\r{1,2}\n[0-9][0-9]/[0-9][0-9]')

admin.sendline('server disable DemoIceStorm-2')
admin.expect('>>>')
admin.sendline('server stop DemoIceStorm-2')
admin.expect('>>>')

time.sleep(3)
sub.expect('[0-9][0-9]/[0-9][0-9].*\r{1,2}\n[0-9][0-9]/[0-9][0-9]')

admin.sendline('server disable DemoIceStorm-3')
admin.expect('>>>')
admin.sendline('server stop DemoIceStorm-3')
admin.expect('>>>')

pub.expect('Ice::NoEndpointException')
pub.waitTestSuccess(1)

sub.kill(signal.SIGINT)
if not demoscript.Util.isCygwin():
    sub.expect('NoEndpointException')
pub.waitTestSuccess(1)
print "ok"

admin.sendline('registry shutdown Master')
admin.sendline('exit')
admin.waitTestSuccess()
node.waitTestSuccess()
#!/usr/bin/env python3

# This file is part of UPSC-SNMP-Agent.
# Copyright (C) 2021 Tom Szilagyi
#
# This program is published under the MIT license;
# see the file LICENSE for the full terms and conditions.
#
# This program is meant to be run by Net-SNMP,
# invoked by the 'pass_persist' extension mechanism.
# To install, put a line like this in /etc/snmp/snmpd.conf:
#
#   pass_persist .1.3.6.1.2.1.33 /usr/bin/python3 /path/to/upsc-snmp-agent.py


#--- CONFIGURATION -------------------------------------------------------

# The name of your UPS according to upsc, so that 'upsc <theUps>' works.
# Alternatively, pass this as the sole argument to this script.
theUps = 'theups'

# Sampling interval in seconds. Requests within the given interval will be
# served from cache, rather than running upsc for each and every query.
sampleInterval = 10

# Default values for upsc variables, used if missing from upsc output.
# For reference, all keys being looked up by the code are listed here;
# those commented out will cause a GET on the corresponding OID to be
# answered with a 'no such object exists' response.
upsDefaults = {
    'battery.charge': 100,
    'battery.charge.warning': 25,
    'battery.current': 0,
    'battery.runtime': 0,
    #'battery.temperature': 37,
    'battery.voltage': 12.0,
    'battery.voltage.low': 10.4,
    'device.mfr': 'PowerWalker',
    'device.model': 'VI 600 SW',
    'driver.version': '1.0',
    'input.current': 0,
    'input.frequency': 50.0,
    'input.frequency.nominal': 50.0,
    'input.realpower': 0,
    'input.transfer.high': 255,
    'input.transfer.low': 210,
    'input.voltage': 230,
    'input.voltage.nominal': 230,
    'output.current': 0,
    'output.frequency': 49.8,
    'output.frequency.nominal': 50,
    'output.realpower': 0,
    'output.voltage': 230,
    'output.voltage.nominal': 230,
    'ups.beeper.status': 'enabled',
    'ups.load': 5,
    'ups.power.nominal': 600,
    'ups.realpower.nominal': 360,
    'ups.start.auto': 'yes',
    'ups.status': 'OL',
}

#--- END CONFIGURATION ---------------------------------------------------

root = '.1.3.6.1.2.1.33'

import subprocess, sys, time

upsData = {}
lastTs = 0

if len (sys.argv) > 1:
    theUps = sys.argv [1]

# MIB format:
#   'oid': ('type', 'value')
# type: one of integer, gauge, counter, timeticks, ipaddress,
#              objectid, octet, or string
# value: literal or lambda returning value
mib = {
    '.1.1.1.0': ('string', lambda: upsGet ('device.mfr')),
    '.1.1.2.0': ('string', lambda: upsGet ('device.model')),
    '.1.1.3.0': ('string', lambda: upsGet ('driver.version')),
    '.1.1.4.0': ('string', 'UPSC-SNMP-Agent'),
    '.1.1.5.0': ('string', theUps),
    '.1.1.6.0': ('string', 'All things connected to this UPS'),

    '.1.2.1.0': ('integer', lambda: upsBatteryStatus ()),
    '.1.2.2.0': ('integer', lambda: int (upsGet ('battery.runtime'))),
   #'.1.2.3.0': upsEstimatedMinutesRemaining
    '.1.2.4.0': ('integer', lambda: upsGet ('battery.charge')),
    '.1.2.5.0': ('integer', lambda: int (10 * upsGet ('battery.voltage'))),
    '.1.2.6.0': ('integer', lambda: int (10 * upsGet ('battery.current'))),
    '.1.2.7.0': ('integer', lambda: int (upsGet ('battery.temperature'))),

   #'.1.3.1.0': # upsInputLineBads
    '.1.3.2.0': ('integer', 1),
    '.1.3.3.1.1.1': ('integer', 1),
    '.1.3.3.1.2.1': ('integer', lambda: int (10 * upsGet ('input.frequency'))),
    '.1.3.3.1.3.1': ('integer', lambda: int (upsGet ('input.voltage'))),
    '.1.3.3.1.4.1': ('integer', lambda: int (10 * upsGet ('input.current'))),
    '.1.3.3.1.5.1': ('integer', lambda: int (upsGet ('input.realpower'))),

    '.1.4.1.0': ('integer', lambda: upsOutputSource ()),
    '.1.4.2.0': ('integer', lambda: int (10 * upsGet ('output.frequency'))),
    '.1.4.3.0': ('integer', 1),
    '.1.4.4.1.1.1': ('integer', 1),
    '.1.4.4.1.2.1': ('integer', lambda: int (upsGet ('output.voltage'))),
    '.1.4.4.1.3.1': ('integer', lambda: int (10 * upsGet ('output.current'))),
    '.1.4.4.1.4.1': ('integer', lambda: int (upsGet ('output.realpower'))),
    '.1.4.4.1.5.1': ('integer', lambda: int (upsGet ('ups.load'))),

    '.1.5.1.0': ('integer', lambda: int (10 * upsGet ('input.frequency'))),
    '.1.5.2.0': ('integer', 0),

    '.1.6.1.0': ('gauge', 0),

    '.1.7.1.0': ('objectid', lambda: '%s.1.7.7.1' % root),
    '.1.7.3.0': ('integer', 6), # no tests initiated

    '.1.8.1.0': ('integer', 1), # output(1), system(2)
    '.1.8.2.0': ('integer', -1),
    '.1.8.3.0': ('integer', -1),
    '.1.8.4.0': ('integer', -1),
    '.1.8.5.0': ('integer', lambda: upsAutoRestart ()),

    '.1.9.1.0': ('integer', lambda: int (upsGet ('input.voltage.nominal'))),
    '.1.9.2.0': ('integer', lambda: int (10 * upsGet ('input.frequency.nominal'))),
    '.1.9.3.0': ('integer', lambda: int (upsGet ('output.voltage.nominal'))),
    '.1.9.4.0': ('integer', lambda: int (10 * upsGet ('output.frequency.nominal'))),
    '.1.9.5.0': ('integer', lambda: int (upsGet ('ups.power.nominal'))),
    '.1.9.6.0': ('integer', lambda: int (upsGet ('ups.realpower.nominal'))),
    #'.1.9.7.0': # upsConfigLowBattTime
    '.1.9.8.0': ('integer', lambda: upsBeeperStatus ()),
    '.1.9.9.0': ('integer', lambda: int (upsGet ('input.transfer.low'))),
    '.1.9.10.0': ('integer', lambda: int (upsGet ('input.transfer.high'))),
}

# on(1), off(2)
def upsAutoRestart ():
    if upsGet ('ups.start.auto') == 'yes':
        return 1
    else:
        return 2

# unknown(1), normal(2), low(3), depleted(4)
def upsBatteryStatus ():
    if upsGet ('battery.voltage') < upsGet ('battery.voltage.low'):
        return 4
    elif upsGet ('ups.status') == 'OB LB':
        return 4
    elif upsGet ('battery.charge') < upsGet ('battery.charge.warning'):
        return 3
    else:
        return 2

# beeper status: disabled(1), enabled(2), muted(3)
def upsBeeperStatus ():
    if upsGet ('ups.beeper.status') == 'enabled':
        return 2
    elif upsGet ('ups.beeper.status') == 'muted':
        return 3
    else:
        return 1

# other(1), none(2), normal(3), bypass(4), battery(5), booster(6), reducer(7)
def upsOutputSource ():
    if upsGet ('ups.status') == 'OL':
        return 3
    elif upsGet ('ups.status') == 'OB':
        return 5
    elif upsGet ('ups.status') == 'OB LB':
        return 5
    else:
        return 1

def upsGet (attr):
    try:
        return upsData [attr]
    except KeyError:
        return upsDefaults [attr]

def getSubOid (sub):
    try:
        v = mib [sub]
        r = v [1]
        if callable (r):
            r = r ()
        print (root + sub)
        print (v [0])
        print (r)
    except KeyError:
        print ("NONE")

def getOid (oid):
    if oid.startswith (root):
        getSubOid (oid [len (root):])
    else:
        print ("NONE")

def convertValue (s):
    try:
        return int (s)
    except ValueError:
        try:
            return float (s)
        except ValueError:
            return s

def cmd (s):
    proc = subprocess.run(s, shell=True, check=True,
                          stdout=subprocess.PIPE, universal_newlines=True)
    return proc.stdout

def upsc ():
    upsData = {}
    data = cmd ('upsc ' + theUps + ' 2>/dev/null')
    data = data.strip ().split ('\n')
    for line in data:
        [key, value] = line.split (':')
        upsData [key.strip ()] = convertValue (value.strip ())
    return upsData

state = 'init'
for line in sys.stdin:
    ts = time.time ()
    if (ts - lastTs > sampleInterval):
        upsData = upsc ()
        lastTs = ts

    arg = line.rstrip ()
    if state == 'init':
        if arg == 'PING':
            print ('PONG')
        elif arg == 'get' or arg == 'getnext' or arg == 'set':
            state = arg
    elif state == 'get':
        getOid (arg)
        state = 'init'
    elif state == 'getnext':
        # Not implemented
        print ("NONE")
        state = 'init'
    elif state == 'set':
        # Not implemented - should save arg as OID to set
        state = 'set_2'
    elif state == 'set_2':
        # Not implemented - should parse type and value from arg
        print ("not-writable")
        state = 'init'
    sys.stdout.flush ()

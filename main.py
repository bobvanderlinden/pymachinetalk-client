#!/usr/bin/env python2
from zeroconfbrowser import ZeroconfBrowser
from machinestatusclient import MachineStatusClient
import zmq

uuid="a42c8c6b-4025-4f83-ba28-dad21114744a"

context = zmq.Context()
context.linger = 0

statusClient = None

def resolveServices(uuid, resolved):
    dsns = {}
    def resolved(tdict):
        service = tdict['service']
        if service in dsns: #once only
            return
        dsn =  tdict['dsn']
        dsns[service] = dsn
        print "resolved", service, dsn #, dsns

def machine_discovered(machine):
    print("Machine found: %s" % (machine.uuid))

def service_discovered(machine, service):
    print("Service found: %s %s %s" % (machine.uuid, service.name, service.dsn))

def initial_discovery_finished(machines):
    print("Found the following machines:")
    print("\n".join(machines.keys()))

    if not uuid in machines:
        print "My machine was not found"
        return
    else:
        print "Found my machine"

    machine = machines[uuid]

    statusClient = MachineStatusClient(context, machine.services["status"].dsn)

browser = ZeroconfBrowser(
    on_machine_discovered = machine_discovered,
    on_service_discovered = service_discovered,
    on_initial_discovery_finished = initial_discovery_finished
    )

import time
while True:
     time.sleep(3)
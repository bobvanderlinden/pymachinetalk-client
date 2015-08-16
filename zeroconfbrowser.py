import sys
import os
from collections import namedtuple
from functools import partial
from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange

# Data types
AvahiServiceDescription = namedtuple("AvahiService", ["interface", "protocol", "name", "service", "domain", "flags"])

Machine = namedtuple("Machine", ["uuid", "services"])
MachineService = namedtuple("MachineService", ["name", "dsn"])

class ZeroconfBrowser():
    """Searches the network for machine services"""
    def __init__(self, loop, on_machine_discovered=None, on_service_discovered=None, on_initial_discovery_finished=None, on_failure=None):
        self.loop = loop
        self.service_browsers = dict()
        self.resolving_services = set()
        self.machines = dict()
        self.on_machine_discovered = on_machine_discovered
        self.on_service_discovered = on_service_discovered
        self.on_initial_discovery_finished = on_initial_discovery_finished
        self.on_failure = on_failure

        self.zeroconf = Zeroconf()

        # machinekit services are here:
        self.browse("_machinekit._tcp.local.")

        # the webtalk server announces _http or _https as configured
        self.browse("_http._tcp.local.")
        self.browse("_https._tcp.local.")

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        self.zeroconf.close()

    def emit_machine_discovered(self, machine):
        if not self.on_machine_discovered is None:
            self.loop.call_soon_threadsafe(self.on_machine_discovered, machine)

    def emit_service_discovered(self, machine, machineService):
        if not self.on_service_discovered is None:
            self.loop.call_soon_threadsafe(self.on_service_discovered, machine, machineService)

    def emit_initial_discovery_finished(self):
        if not self.on_initial_discovery_finished is None:
            self.loop.call_soon_threadsafe(self.on_initial_discovery_finished)

    def emit_failure(self, error):
        if not self.on_failure is None:
            self.loop.call_soon_threadsafe(self.on_failure, error)

    def browse(self, serviceName):
        if serviceName in self.service_browsers:
            return

        browser = ServiceBrowser(self.zeroconf, serviceName, handlers=[self.on_service_state_change])
        self.service_browsers[serviceName] = browser

    def on_service_state_change(self, zeroconf, service_type, name, state_change):
        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                self.on_service_added(zeroconf, service_type, name, info)

        elif state_change is ServiceStateChange.Removed:
            # TODO: Implement
            pass

    def on_service_added(self, zeroconf, service_type, name, info):
        # Validate service info.
        if not info.properties:
            return
        if b"uuid" not in info.properties:
            return
        if b"service" not in info.properties:
            return
        if b"dsn" not in info.properties:
            return

        # Retrieve wanted properties from service info.
        uuid = info.properties[b"uuid"].decode('utf-8')
        dsn = info.properties[b"dsn"].decode('utf-8')
        service = info.properties[b"service"].decode('utf-8')

        # See if machine was already discovered.
        if not uuid in self.machines:
            machine = Machine(uuid = uuid, services = dict())
            self.machines[uuid] = machine

            # Notify consumer about discovered machine.
            self.emit_machine_discovered(machine)

        machine = self.machines[uuid]

        # We found a new machine service.
        machineService = MachineService(
            name = service,
            dsn = dsn
            )
        machine.services[machineService.name] = machineService
        self.emit_service_discovered(machine, machineService)

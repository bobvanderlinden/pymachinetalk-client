import sys
import os
import dbus
from dbus.mainloop.glib import DBusGMainLoop
import avahi
import gobject
import threading
from collections import namedtuple
from functools import partial

# TODO: Do we need this here?
gobject.threads_init()
dbus.mainloop.glib.threads_init()

# Data types
AvahiServiceDescription = namedtuple("AvahiService", ["interface", "protocol", "name", "service", "domain", "flags"])

Machine = namedtuple("Machine", ["uuid", "services"])
MachineService = namedtuple("MachineService", ["name", "dsn"])

class ZeroconfBrowser():
    """Searches the network for machine services"""
    def __init__(self, on_machine_discovered=None, on_service_discovered=None, on_initial_discovery_finished=None, on_failure=None):
        self.service_browsers = set()
        self.resolving_services = set()
        self.discovery_finshed = False
        self.machines = dict()
        self.on_machine_discovered = on_machine_discovered
        self.on_service_discovered = on_service_discovered
        self.on_initial_discovery_finished = on_initial_discovery_finished
        self.on_failure = on_failure
        self.lock = threading.Lock()

        # TODO: Make sure this isn't this a global loop.
        loop = DBusGMainLoop(set_as_default=True)
        self._bus = dbus.SystemBus(mainloop=loop)
        self.server = dbus.Interface(
                self._bus.get_object(avahi.DBUS_NAME, avahi.DBUS_PATH_SERVER),
                avahi.DBUS_INTERFACE_SERVER
                )

        thread = threading.Thread(target=gobject.MainLoop().run)
        thread.daemon = True
        thread.start()

        # machinekit services are here:
        self.browse("_machinekit._tcp")

        # the webtalk server announces _http or _https as configured
        self.browse("_http._tcp")
        self.browse("_https._tcp")

    def browse(self, service):
        if service in self.service_browsers:
            return
        self.service_browsers.add(service)

        with self.lock:
            browser = dbus.Interface(self._bus.get_object(avahi.DBUS_NAME,
                    self.server.ServiceBrowserNew(avahi.IF_UNSPEC,
                            avahi.PROTO_UNSPEC, service, "local", dbus.UInt32(0))),
                    avahi.DBUS_INTERFACE_SERVICE_BROWSER)

            browser.connect_to_signal("ItemNew", self.item_new)
            browser.connect_to_signal("AllForNow", self.all_for_now)
            browser.connect_to_signal("Failure", self.failure)

    def pair_to_dict(self, l):
        ''' helper to parse TXT record into dict '''
        res = dict()
        for el in l:
            if "=" not in el:
                res[el]=''
            else:
                tmp = el.split('=',1)
                if len(tmp[0]) > 0:
                    res[tmp[0]] = tmp[1]
        return res

    def item_new(self, interface, protocol, name, service, domain, flags):
        with self.lock:
            avahiServiceDescription = AvahiServiceDescription(interface, protocol, name, service, domain, flags)
            self.resolving_services.add(avahiServiceDescription)
            self.server.ResolveService(
                    interface,
                    protocol,
                    name,
                    service,
                    domain,
                    avahi.PROTO_UNSPEC,
                    dbus.UInt32(0),
                    reply_handler=self.resolved,
                    error_handler=partial(self.resolve_error, avahiServiceDescription)
                    )

    def all_for_now(self):
        with self.lock:
            if self.discovery_finshed:
                return
            self.discovery_finshed = True

            # Check whether we are done resolving/discovering all machines.
            self.checkAllForNow()

    def checkAllForNow(self):
        if self.discovery_finshed and len(self.resolving_services) == 0:
            if not self.on_initial_discovery_finished is None:
                self.on_initial_discovery_finished(self.machines)

    def failure(self, exception):
        if not self.on_failure is None:
            self.on_failure(exception)

    def resolved(self, interface, protocol, name, service, domain, host,
            aprotocol, address, port, txt, flags):
        avahiServiceDescription = AvahiServiceDescription(interface, protocol, name, service, domain, flags)
        if not avahiServiceDescription in self.resolving_services:
            # The service was already removed. No need to do anything with the resolved service information.
            return
        self.resolving_services.remove(avahiServiceDescription)

        self.handleTxtEntry(txt)

        # Check whether we are done resolving/discovering all machines.
        self.checkAllForNow()

    def handleTxtEntry(self, txt):
        # Check whether all required machine attributes are in the txt field.
        tr = self.pair_to_dict(avahi.txt_array_to_string_array(txt))
        if not "uuid" in tr:
            return
        if not "dsn" in tr:
            return
        if not "service" in tr:
            return

        # We found a valid Machinekit service.

        uuid = tr["uuid"]
        dsn = tr["dsn"]
        service = tr["service"]

        # Check if the service belongs to a new machine.
        if not uuid in self.machines:
            machine = Machine(uuid = uuid, services = dict())
            self.machines[uuid] = machine
            if not self.on_machine_discovered is None:
                self.on_machine_discovered(machine)

        machine = self.machines[uuid]

        # We found a new machine service.
        machineService = MachineService(
            name = service,
            dsn = dsn
            )
        machine.services[machineService.name] = machineService
        if not self.on_service_discovered is None:
            self.on_service_discovered(machine, machineService)

    def resolve_error(self, avahiServiceDescription, *args, **kwargs):
        if not avahiServiceDescription in self.resolving_services:
            return
        self.resolving_services.remove(avahiServiceDescription)

        # Check whether we are done resolving/discovering all machines.
        self.checkAllForNow()

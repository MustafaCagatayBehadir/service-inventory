"""Service-Inventory Main Module."""
import os
import inspect
import ncs
import _ncs
from ncs.application import Service

INDENTATION = " "
USER = "admin"


def get_kp_service_id(keypath: ncs.maagic.keypath._KeyPath) -> str:
    """Get service name from keypath."""
    kpath = str(keypath)
    service = kpath[kpath.rfind("{") + 1 : len(kpath) - 1]
    return service


# ------------------------
# Action CALLBACK
# ------------------------
class OobDiscovery(ncs.dp.Action):
    """Service-Inventory Discovery Action Class."""

    @ncs.dp.Action.action
    def cb_action(self, uinfo, name, kp, input, output, trans):
        """Discover service."""
        self.log.info("Action triggered ##" + INDENTATION + name)
        _ncs.dp.action_set_timeout(uinfo, 1800)
        service_inventory_name = get_kp_service_id(kp)
        self.log.info("Discovery Service Inventory  ##" + INDENTATION + service_inventory_name)
        output.status = "success"

        # Check environment setting for IPC port value
        port = int(os.getenv("NCS_IPC_PORT", ncs.NCS_PORT))
        self.log.info("Using NCS IPC port value ##" + INDENTATION + str(port))
        self.populate_service_inventory_manager_service_list(service_inventory_name)
        self.populate_service_inventory_manager_device_list(service_inventory_name)
        return ncs.CONFD_OK

    def populate_service_inventory_manager_service_list(self, service_inventory_name):
        """Populate service-inventory-manager service list."""
        self.log.info("Function ##" + INDENTATION + inspect.stack()[0][3])
        with ncs.maapi.single_write_trans(USER, "system") as trans:
            root = ncs.maagic.get_root(trans, shared=False)
            service_inventory = root.srvc_inv__service_inventory_manager[service_inventory_name]
            template = ncs.template.Template(service_inventory)
            tvars = ncs.template.Variables()
            tvars.add("INVENTORY", service_inventory_name)
            template.apply("service-inventory-service-l2vpn-template", tvars)
            trans.apply()

    def populate_service_inventory_manager_device_list(self, service_inventory_name):
        """Populate service-inventory-manager device list."""
        self.log.info("Function ##" + INDENTATION + inspect.stack()[0][3])
        with ncs.maapi.single_write_trans(USER, "system") as trans:
            root = ncs.maagic.get_root(trans, shared=False)
            service_inventory = root.srvc_inv__service_inventory_manager[service_inventory_name]
            template = ncs.template.Template(service_inventory)
            tvars = ncs.template.Variables()
            tvars.add("INVENTORY", service_inventory_name)
            template.apply("service-inventory-device-l2vpn-template", tvars)
            trans.apply()


# ------------------------
# SERVICE CALLBACK
# ------------------------
class ServiceInventoryCallbacks(Service):
    """Service class."""

    @Service.create
    def cb_create(self, tctx, root, service, proplist):
        """Create method for service."""
        self.log.info("Provisioning service-inventory group ", service.name)
        # template = ncs.template.Template(service)
        # template.apply("service-inventory-l2vpn-template")


# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS.
# ---------------------------------------------
class Main(ncs.application.Application):
    """Service-Inventory main class."""

    def setup(self):
        """Register service and actions."""
        self.log.info("Main RUNNING")

        # servce-inventory service registration
        self.register_service("service-inventory-servicepoint", ServiceInventoryCallbacks)

        self.register_action("oob-discovery-point", OobDiscovery)

    def teardown(self):
        """Teardown."""
        self.log.info("Main FINISHED")

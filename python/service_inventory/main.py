"""Service-Inventory Main Module."""
import inspect
import os

import _ncs
import ncs
from ncs.application import Service

INDENTATION = " "
USER = "admin"


def get_kp_service_id(keypath: ncs.maagic.keypath._KeyPath) -> str:
    """Get service name from keypath."""
    kpath = str(keypath)
    service = kpath[kpath.rfind("{") + 1 : kpath.rfind("}")]
    return service


def prepare_device_dry_run(device_name, config_changes, log) -> str:
    """Build dry-run changes string for given device."""
    log.info(f"collecting dry run changes for {device_name}")

    result = f"\n\n################ Device: {device_name} ################\n\n"
    result += str(config_changes)
    result += "\n"

    return result


def commit_config(input, commit_params, trans, log) -> str:
    """Process commit parameters and report the result."""
    result = ""

    if input.dry_run:
        commit_params.dry_run_native()
        log.info("providing dry run changes")
        dry_output = trans.apply_params(True, commit_params)
        if "device" in dry_output:
            for device in dry_output["device"]:
                result += prepare_device_dry_run(device, dry_output["device"][device], log)
        else:
            result += "no changes\n"
        return result

    log.info("committing the changes")
    trans.apply_params(True, commit_params)
    return result


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
        self.log.info("Service Inventory Discovery  ##" + INDENTATION + service_inventory_name)
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
            root = ncs.maagic.get_root(trans)
            service_inventory = root.srvc_inv__service_inventory_manager[service_inventory_name]
            template = ncs.template.Template(service_inventory)
            template.apply("service-inventory-service-l2vpn-template")
            trans.apply()

    def populate_service_inventory_manager_device_list(self, service_inventory_name):
        """Populate service-inventory-manager device list."""
        self.log.info("Function ##" + INDENTATION + inspect.stack()[0][3])
        with ncs.maapi.single_write_trans(USER, "system") as trans:
            root = ncs.maagic.get_root(trans)
            service_inventory = root.srvc_inv__service_inventory_manager[service_inventory_name]
            template = ncs.template.Template(service_inventory)
            template.apply("service-inventory-device-l2vpn-template")
            trans.apply()


# ------------------------
# Action CALLBACK
# ------------------------
class OobReconcile(ncs.dp.Action):
    """Service-Inventory Reconcile Action Class."""

    @ncs.dp.Action.action
    def cb_action(self, uinfo, name, kp, input, output, trans):
        """Reconcile service."""
        self.log.info("Action triggered ##" + INDENTATION + name)
        _ncs.dp.action_set_timeout(uinfo, 1800)
        service_inventory_name = get_kp_service_id(kp)
        self.log.info("Service Inventory Reconcile  ##" + INDENTATION + service_inventory_name)
        output.result = ""

        # Check environment setting for IPC port value
        port = int(os.getenv("NCS_IPC_PORT", ncs.NCS_PORT))
        self.log.info("Using NCS IPC port value ##" + INDENTATION + str(port))
        commit_result = self.populate_l2vpn_elan_list(service_inventory_name, input)
        if commit_result == "":
            output.result += "\nNothing will push to the network."
        else:
            output.result += commit_result

    def populate_l2vpn_elan_list(self, service_inventory_name, input):
        """Populate l2vpn elan services with reconcile no-networking."""
        self.log.info("Function ##" + INDENTATION + inspect.stack()[0][3])
        with ncs.maapi.single_write_trans(USER, "system") as trans:
            root = ncs.maagic.get_root(trans)
            service_inventory = root.srvc_inv__service_inventory_manager[service_inventory_name]
            template = ncs.template.Template(service_inventory)
            template.apply("service-inventory-l2vpn-elan-template")
            commit_params = ncs.maapi.CommitParams()
            commit_params.reconcile_keep_non_service_config()
            commit_result = commit_config(input, commit_params, trans, self.log)
            return commit_result


# ------------------------
# SERVICE CALLBACK
# ------------------------
class ServiceInventoryCallbacks(Service):
    """Service class."""

    @Service.create
    def cb_create(self, tctx, root, service, proplist):
        """Create method for service."""
        self.log.info("Provisioning service-inventory group ", service.name)
        template = ncs.template.Template(service)
        template.apply("service-inventory-service-l2vpn-template")
        template.apply("service-inventory-device-l2vpn-template")
        template.apply("service-inventory-l2vpn-elan-template")


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

        # servce-inventory discovery action registration
        self.register_action("oob-discovery-point", OobDiscovery)

        # servce-inventory reconcile action registration
        self.register_action("oob-reconcile-point", OobReconcile)

    def teardown(self):
        """Teardown."""
        self.log.info("Main FINISHED")

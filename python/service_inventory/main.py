"""Service-Inventory Main Module."""
import inspect
import os
from typing import List

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


def prepare_device_dry_run(device_name: str, config_changes: str, log: ncs.log.Log) -> str:
    """Build dry-run changes string for given device."""
    log.info(f"collecting dry run changes for {device_name}")

    result = f"\n\n################ Device: {device_name} ################\n\n"
    result += str(config_changes)
    result += "\n"

    return result


def commit_config(
    input: ncs.maagic.Container, commit_params: ncs.maapi.CommitParams, trans: ncs.maapi.Transaction, log: ncs.log.Log
) -> str:
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

    def populate_service_inventory_manager_service_list(self, service_inventory_name: str):
        """Populate service-inventory-manager service list."""
        self.log.info("Function ##" + INDENTATION + inspect.stack()[0][3])
        with ncs.maapi.single_write_trans(USER, "system") as trans:
            root = ncs.maagic.get_root(trans)
            service_inventory = root.srvc_inv__service_inventory_manager[service_inventory_name]
            template = ncs.template.Template(service_inventory)
            template.apply("service-inventory-service-l2vpn-template")
            trans.apply()

    def populate_service_inventory_manager_device_list(self, service_inventory_name: str):
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

    def populate_l2vpn_elan_list(self, service_inventory_name: str, input: ncs.maagic.Container) -> str:
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
# Action CALLBACK
# ------------------------
class OobMigration(ncs.dp.Action):
    """Service-Inventory Migration Action Class."""

    @ncs.dp.Action.action
    def cb_action(self, uinfo, name, kp, input, output, trans):
        """Migrate service."""
        self.log.info("Action triggered ##" + INDENTATION + name)
        _ncs.dp.action_set_timeout(uinfo, 1800)
        service_inventory_name = get_kp_service_id(kp)
        self.log.info("Service Inventory Migration  ##" + INDENTATION + service_inventory_name)
        output.result = ""

        source = input.source
        src_dev, src_if_size, src_if_number = source.device, source.if_size, source.if_number
        destination = input.destination
        dest_dev, dest_if_size, dest_if_number = destination.device, destination.if_size, destination.if_number
        root = ncs.maagic.get_root(trans)

        if input.service == "l2vpn":
            elan_srv_names = self.get_l2vpn_elan_service_names(
                service_inventory_name, src_dev, src_if_size, src_if_number, root
            )
            output.result += self.migrate_l2vpn_elan_service_nodes(
                elan_srv_names,
                src_dev,
                src_if_size,
                src_if_number,
                dest_dev,
                dest_if_size,
                dest_if_number,
                input,
            )

    def get_l2vpn_elan_service_names(
        self, service_inventory_name: str, device: str, if_size: str, if_number: str, root: ncs.maagic.Root
    ) -> List[str]:
        """Get source device l2vpn elan service nodes."""
        self.log.info("Function ##" + INDENTATION + inspect.stack()[0][3])
        service_inventory = root.srvc_inv__service_inventory_manager[service_inventory_name]
        srvc_inv_dev_intf = service_inventory.srvc_inv__devices.device[device].interface[if_size, if_number]
        srvc_inv_dev_intf_l2vpn = srvc_inv_dev_intf.srvc_inv__service["l2vpn"]

        elan_srv_names = []
        for elan in srvc_inv_dev_intf_l2vpn.elan:
            elan_name = elan.name
            elan_srv_names.append(elan_name)
            self.log.info("Elan ##" + INDENTATION * 2 + elan_name + " is added to elan service name list.")
        return elan_srv_names

    def migrate_l2vpn_elan_service_nodes(
        self,
        elan_srv_names: List[str],
        src_dev: str,
        src_if_size: str,
        src_if_number: str,
        dest_dev: str,
        dest_if_size: str,
        dest_if_number: str,
        input: ncs.maagic.Container,
    ):
        """Migrate l2vpn elan endpoint interface configurations."""
        self.log.info("Function ##" + INDENTATION + inspect.stack()[0][3])

        with ncs.maapi.single_write_trans(USER, "system") as trans:
            root = ncs.maagic.get_root(trans)
            l2vpn = root.l2vpn__l2vpn
            for elan_name in elan_srv_names:
                elan_srv = l2vpn.l2vpn__elan[elan_name]
                template = ncs.template.Template(elan_srv)
                tvars = ncs.template.Variables()
                tvars.add("SRC_DEVICE", src_dev)
                tvars.add("SRC_IF_SIZE", src_if_size)
                tvars.add("SRC_IF_NUMBER", src_if_number)
                tvars.add("DEST_DEVICE", dest_dev)
                tvars.add("DEST_IF_SIZE", dest_if_size)
                tvars.add("DEST_IF_NUMBER", dest_if_number)
                self.log.info(
                    "Elan ##"
                    + INDENTATION * 2
                    + elan_name
                    + " service-inventory-migration-l2vpn-elan-template is applying..."
                )
                template.apply("service-inventory-migration-l2vpn-elan-template", tvars)
                self.log.info(
                    "Elan ##"
                    + INDENTATION * 2
                    + elan_name
                    + " service-inventory-migration-l2vpn-elan-template is applied."
                )
            commit_params = ncs.maapi.CommitParams()
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

        # servce-inventory migration action registration
        self.register_action("oob-migration-point", OobMigration)

    def teardown(self):
        """Teardown."""
        self.log.info("Main FINISHED")

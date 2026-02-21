import os
from pathlib import Path
import pulumi
import pulumi_gcp as gcp

# Read config
config = pulumi.Config("gcp")
project = config.require("project")
region = config.get("region") or "us-central1"
zone = config.get("zone") or "us-central1-a"

ssh_user = "ubuntu"
ssh_pub_key = Path(os.path.expanduser("~/.ssh/id_rsa.pub")).open().read().strip()

# VPC Network
vpc = gcp.compute.Network(
    "lab04-vpc",
    name="lab04-vpc",
    auto_create_subnetworks=False,
)

# Subnet
subnet = gcp.compute.Subnetwork(
    "lab04-subnet",
    name="lab04-subnet",
    ip_cidr_range="10.0.1.0/24",
    region=region,
    network=vpc.id,
)

# Firewall
firewall = gcp.compute.Firewall(
    "lab04-allow-ssh-http",
    name="lab04-allow-ssh-http",
    network=vpc.name,
    allows=[
        gcp.compute.FirewallAllowArgs(
            protocol="tcp",
            ports=["22", "80", "5000"],
        )
    ],
    source_ranges=["0.0.0.0/0"],
    target_tags=["lab04-vm"],
)

# VM
vm = gcp.compute.Instance(
    "lab04-vm",
    name="lab04-vm",
    machine_type="e2-micro",
    zone=zone,
    tags=["lab04-vm"],
    boot_disk=gcp.compute.InstanceBootDiskArgs(
        initialize_params=gcp.compute.InstanceBootDiskInitializeParamsArgs(
            image="ubuntu-os-cloud/ubuntu-2204-lts",
            size=20,
        )
    ),
    network_interfaces=[
        gcp.compute.InstanceNetworkInterfaceArgs(
            network=vpc.id,
            subnetwork=subnet.id,
            access_configs=[gcp.compute.InstanceNetworkInterfaceAccessConfigArgs()],
        )
    ],
    metadata={
        "ssh-keys": f"{ssh_user}:{ssh_pub_key}",
    },
)

# Outputs
pulumi.export("public_ip", vm.network_interfaces[0].access_configs[0].nat_ip)
pulumi.export(
    "ssh_command",
    pulumi.Output.concat(
        "ssh ubuntu@", vm.network_interfaces[0].access_configs[0].nat_ip
    ),
)

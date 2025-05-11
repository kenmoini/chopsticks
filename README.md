# Chopsticks - for sushy-tools

[sushy-tools](https://docs.openstack.org/sushy-tools/latest/user/dynamic-emulator.html) is a great tool that extends VMs running on Libvirt/ESXi with Redfish functionality for controlling the power state and attached virtual media.

However, you have to reference the VMs by the KVM UUID which is not so flexible.

**Chopsticks aims to solve that** - you can now use Chopsticks in front of sushy-tools and use VM names in a variety of targeting patterns.

## Operating Modes

- **Wildcard** - This is where your VM names are used as wildcard subdomains, eg `vm-name-here.chopsticks.example.com/redfish/v1/Systems/1/...`.
- **Subdirectory** - The VM name is prefixed to the base API path, eg `chopsticks.example.com/vm-name-here/redfish/v1/Systems/1/...`
- **Path** - The VM name is substituted for the System UUID itself, eg `chopsticks.example.com/redfish/v1/Systems/vm-name-here/...`

The operating mode can be controlled by setting the `CHOPSTICKS_ENDPOINT_MODE` environment variable to either `wildcard`, `subdirectory`, or `path`.  By default Chopsticks operates in `path` mode, since that is the easiest for most deployments and mapping.

## Deployment

> sushy-tools should already be deployed

### Command Line

```bash
# Clone this repo
git clone https://github.com/kenmoini/chopsticks
cd chopsticks

# Install the needed Python 3 modules
python3 -m pip install -r src/requirements.txt

# Export mandatory variables
export SUSHY_TOOLS_ENDPOINT="http://sushy-tools.example.com:8111"

# Export optional variables
export CHOPSTICKS_ENDPOINT_MODE=path
export FLASK_RUN_PORT=3434

# Run the python server
python3 src/chopsticks.py
```

### Container

```bash
# Run the container?
podman run --rm -d --name chopsticks \
 -e SUSHY_TOOLS_ENDPOINT="http://sushy-tools.example.com:8111" \
 -e FLASK_RUN_PORT=3434 \
 -e CHOPSTICKS_ENDPOINT_MODE=path \
 -p 3434:3434/tcp \
 -v /var/run/libvirt:/var/run/libvirt:ro \
 --user 0 \
 quay.io/kenmoini/chopsticks:latest
```

Yes, the container needs to be run as a root user - socket things.  Could probably be bypassed with a `qemu+ssh` connection with the `LIBVIRT_ENDPOINT` environment variable.
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import requests
import json
from urllib.parse import urlparse
import libvirt
import sys
import os

# This is a simple Flask application that acts as a proxy for Sushy-tools
# It translates VM names into the appropriate UUIDs for the Sushy-tools API
# It can operate in three modes:
# 1. Wildcard mode: The VM name is extracted from the hostname (e.g., vm-name.chopsticks.example.com/redfish/v1/.../1/...)
# 2. Subdirectory mode: The VM name is extracted from the URL path (e.g., chopsticks.example.com/vm-name/redfish/v1/.../1/...)
# 3. Path mode: The VM name is substituted as the System ID (eg chopsticks.example.com/redfish/v1/.../vm-name/...)

##############################
# Setup Flask Variables
flaskDebug = os.environ.get("FLASH_DEBUG", False)
flaskPort = os.environ.get("FLASK_RUN_PORT", 3434)
flaskHost = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
tlsCert = os.environ.get("FLASK_TLS_CERT", "")
tlsKey = os.environ.get("FLASK_TLS_KEY", "")

##############################
# Chopsticks Variables
endpointMode = os.environ.get('CHOPSTICKS_ENDPOINT_MODE', 'path') # path, wildcard, or subdirectory
sushyToolsEndpoint = os.environ.get('SUSHY_TOOLS_ENDPOINT', 'http://sushy-tools.example.com:8111') # Default Sushy-tools endpoint
libvirtEndpoint = os.environ.get('LIBVIRT_ENDPOINT', 'qemu:///system')

##############################
# System Defaults
systemPath = os.environ.get('SYSTEM_PATH', '/redfish/v1/Systems/') # Default system path
managerPath = os.environ.get('MANAGER_PATH', '/redfish/v1/Managers/') # Default manager path
chassisPath = os.environ.get('CHASSIS_PATH', '/redfish/v1/Chassis/') # Default chassis path
idNumber = os.environ.get('ID_NUMBER', '1') # Default ID number

##############################
# creates a Flask application
app = Flask(__name__)
CORS(app) # This will enable CORS for all routes

####################################################################################################
# Index Page
@app.route("/")
def index():
    return f"Chopsticks is a Sushy-tools proxy for easy host translation - operating in {endpointMode} mode."

####################################################################################################
# Health check endpoint
@app.route("/healthz", methods = ['GET'])
def healthz():
    if request.method == 'GET':
        return "ok"

####################################################################################################
# Chopsticks Entrypoint
@app.route("/<path:route>")
def entrypoint(route):
    # Parse the request URL
    url = urlparse(request.base_url)
    requestMethod = request.method
    # Get the server hostname and path
    serverHostname = url.hostname
    path = url.path.lstrip('/')
    newPath = path
    #print(f"Server hostname: {serverHostname}, path: {path}")
    vmUUIDReplacement = idNumber
    
    # Wildcard Mode - vm-name.chopsticks.example.com/redfish/v1/...
    if endpointMode == "wildcard":
        # Get the first part of the hostname
        targetVM = serverHostname.split('.')[0]
        # Get the VM
        vmInfo = getVMFromName(targetVM)
        if vmInfo is None:
            return f"Target VM {targetVM} not found in list of VMs: {getLibvirtVMs()}", 404

        vmUUID = vmInfo['uuid']
        #print(f"Target VM: {targetVM} - {vmUUID}")
        # If we're not really doing anything then just proxy the request
        # Proxy base request
        if path.strip("/") in ["redfish", "redfish/v1", "redfish/v1/Systems", "redfish/v1/Managers", "redfish/v1/Chassis"]:
            req = proxyRequest(sushyToolsEndpoint + "/" + path, requestMethod)
            sushyTransaction = sushyToolsReturnFilter(req, vmUUID, vmUUIDReplacement)
            return jsonify(json.loads(sushyTransaction)), req.status_code
            #return req.content, req.status_code
        else:
            newPath = '/'.join(path.split('/')[0:3]) + '/' + vmUUID + '/' + '/'.join(path.split('/')[5:])
            sushyToolsServer = f"{sushyToolsEndpoint}/{newPath}"

        sushyRequest = proxyRequest(sushyToolsServer, requestMethod)
        sushyTransaction = sushyToolsReturnFilter(sushyRequest, vmUUID, vmUUIDReplacement)
        return jsonify(json.loads(sushyTransaction)), sushyRequest.status_code

    # Subdirectory Mode - chopsticks.example.com/vm-name/redfish/v1/...
    elif endpointMode == "subdirectory":
        targetVM = path.split('/')[0] if len(path.split('/')) > 1 else None
        # Get the VM
        vmInfo = getVMFromName(targetVM)
        if vmInfo is None:
            return f"Target VM {targetVM} not found in list of VMs: {getLibvirtVMs()}", 404

        vmUUID = vmInfo['uuid']
        #print(f"Target VM: {targetVM} - {vmUUID}")
        # If we're not really doing anything then just proxy the request
        remainingPath = path.split('/')[1:] if len(path.split('/')) > 1 else None
        remainingPath = '/'.join(remainingPath)
        if remainingPath.strip("/") in ["redfish", "redfish/v1", "redfish/v1/Systems", "redfish/v1/Managers", "redfish/v1/Chassis"]:
            req = proxyRequest(sushyToolsEndpoint + "/" + remainingPath, requestMethod)
            sushyTransaction = sushyToolsReturnFilterSubdir(req, vmUUID, vmUUIDReplacement, targetVM)
            return jsonify(json.loads(sushyTransaction)), req.status_code
        else:
            newPath = '/'.join(path.split('/')[1:4]) + '/' + vmUUID + '/' + '/'.join(path.split('/')[5:])
            sushyToolsServer = f"{sushyToolsEndpoint}/{newPath}"

        sushyRequest = proxyRequest(sushyToolsServer, requestMethod)
        sushyTransaction = sushyToolsReturnFilterSubdir(sushyRequest, vmUUID, vmUUIDReplacement, targetVM)
        return jsonify(json.loads(sushyTransaction)), sushyRequest.status_code

    elif endpointMode == "path":
        # Path mode - chopsticks.example.com/redfish/v1/{Systems,Managers,Chassis}/vm-name/...
        # Split the path
        pathParts = path.split('/')
        # Get the target VM from the path
        targetVM = pathParts[3] if (len(pathParts) > 3 and pathParts[3] != "") else None

        # Get the VM
        vmInfo = getVMFromName(targetVM)
        if vmInfo is None:
            if path.strip("/") in ["redfish", "redfish/v1", "redfish/v1/Systems", "redfish/v1/Managers", "redfish/v1/Chassis"]:
                req = proxyRequest(sushyToolsEndpoint + "/" + path, requestMethod)
                sushyTransaction = vmUUIDListingFilter(req)
                return jsonify(json.loads(sushyTransaction)), req.status_code
            return f"Target VM {targetVM} not found in list of VMs: {getLibvirtVMs()}", 404

        vmUUID = vmInfo['uuid']
        newPath = path.replace(targetVM, vmUUID)
        vmUUIDReplacement = targetVM
        sushyToolsServer = f"{sushyToolsEndpoint}/{newPath}"

        sushyRequest = proxyRequest(sushyToolsServer, requestMethod)
        sushyTransaction = sushyToolsReturnFilter(sushyRequest, vmUUID, vmUUIDReplacement)
        return jsonify(json.loads(sushyTransaction)), sushyRequest.status_code

    else:
        # Invalid endpoint mode
        return "Invalid endpoint mode", 400
    if targetVM is None:
        return "Target VM not specified", 400

####################################################################################################
# Gets information about a VM from Libvirt and returns the data
def getVMFromName(targetVM):
    # Check if the target VM is valid
    vms = getLibvirtVMs()
    foundVM = False
    selectedVM = None
    for vm in vms:
        if vm['name'] == targetVM:
            foundVM = True
            selectedVM = vm
            break
    return selectedVM

####################################################################################################
# This function proxies the request to the Sushy-tools server
def proxyRequest(sushyToolsServer, requestMethod):
    # Make a request to the sushyToolsServer
    match requestMethod:
        case 'GET':
            # Handle GET request
            sushyRequest = requests.get(sushyToolsServer)
        case 'POST':
            # Handle POST request
            sushyRequest = requests.post(sushyToolsServer, data=request.data)
        case 'PUT':
            # Handle PUT request
            sushyRequest = requests.put(sushyToolsServer, data=request.data)
        case 'DELETE':
            # Handle DELETE request
            sushyRequest = requests.delete(sushyToolsServer)
        case 'PATCH':
            # Handle PATCH request
            sushyRequest = requests.patch(sushyToolsServer, data=request.data)
        case 'OPTIONS':
            # Handle OPTIONS request
            sushyRequest = requests.options(sushyToolsServer)
        case 'HEAD':
            # Handle HEAD request
            sushyRequest = requests.head(sushyToolsServer)
        case _:
            # Handle unsupported request method
            return "Unsupported request method", 405

    return sushyRequest


####################################################################################################
# Get the list of VMs from libvirt
# This function returns a list of VMs with their names, UUIDs, and states
def getLibvirtVMs():    
    try:
        #conn = libvirt.openReadOnly(None)
        conn = libvirt.openReadOnly(libvirtEndpoint)
        createdOffVMs = conn.listDefinedDomains()
        vms = []
        for name in createdOffVMs:
            vm = conn.lookupByName(name)
            vms.append({
                'name': name,
                'uuid': vm.UUIDString(),
                'state': vm.isActive()
            })
        
        active_hosts = conn.listDomainsID()
        for id in active_hosts:
            vm = conn.lookupByID(id)
            vms.append({
                'name': vm.name(),
                'uuid': vm.UUIDString(),
                'state': vm.isActive()
            })
        conn.close()
        return vms
    except libvirt.libvirtError:
        print('Failed to open connection to the hypervisor')
        sys.exit(1)

####################################################################################################
# This is a dirty function plz dont look
def sushyToolsReturnFilter(sushyRequest, uuid, replacement):
    # Stringify the response
    stringifiedResponse = json.dumps(sushyRequest.text)
    # Replace the UUID in the response with the replacement string
    stringifiedResponse = stringifiedResponse.replace(uuid, replacement)
    # Parse the stringified response back to JSON
    jsonResponse = json.loads(stringifiedResponse)
    return jsonResponse

# This is a dirty function plz dont look
def sushyToolsReturnFilterSubdir(sushyRequest, uuid, replacement, prefix):
    # Stringify the response
    stringifiedResponse = json.dumps(sushyRequest.text)
    # Replace the UUID in the response with the replacement string
    stringifiedResponse = stringifiedResponse.replace(uuid, replacement)
    # Prefix the redfish paths
    stringifiedResponse = stringifiedResponse.replace("redfish/v1/", prefix + "/redfish/v1/")
    # Parse the stringified response back to JSON
    jsonResponse = json.loads(stringifiedResponse)
    return jsonResponse

# This is a dirty function plz dont look
# This function will take the response from Sushy tools and replace any UUID matching any VM
# Used for path-mode System/Manager/Chassis listing
def vmUUIDListingFilter(sushyRequest):
    # Stringify the response
    stringifiedResponse = json.dumps(sushyRequest.text)
    # Get all the VMs
    vmListing = getLibvirtVMs()
    # Loop through the VMs and replace any UUIDs
    for vm in vmListing:
        stringifiedResponse = stringifiedResponse.replace(vm['uuid'], vm['name'])
    # Parse the stringified response back to JSON
    jsonResponse = json.loads(stringifiedResponse)
    return jsonResponse

####################################################################################################
if __name__ == "__main__":
    if tlsCert != "" and tlsKey != "":
        print("Starting Chopsticks on port " + str(flaskPort) + " and host " + str(flaskHost) + " with TLS cert " + str(tlsCert) + " and TLS key " + str(tlsKey))
        app.run(debug=flaskDebug, ssl_context=(str(tlsCert), str(tlsKey)), port=flaskPort, host=flaskHost)
    else:
        print("Starting Chopsticks on port " + str(flaskPort) + " and host " + str(flaskHost))
        app.run(debug=flaskDebug, port=flaskPort, host=flaskHost)

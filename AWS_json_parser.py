# NOTE: this is a Proof of Concept script, please test before using in production!

# Copyright (c) 2019 Cisco and/or its affiliates.
# This software is licensed to you under the terms of the Cisco Sample
# Code License, Version 1.0 (the "License"). You may obtain a copy of the
# License at
#                https://developer.cisco.com/docs/licenses
# All use of the material herein must be in accordance with the terms of
# the License. All rights not expressly granted by the License are
# reserved. Unless required by applicable law or agreed to separately in
# writing, software distributed under the License is distributed on an "AS
# IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.

import getpass
import json
import os
import requests
import sys
import datetime
import time
import uuid

# import supporting functions from additional file
from Firepower import Firepower

# Config Paramters
CONFIG_FILE     = "config_file.json"
CONFIG_DATA     = None

# Object Prefix
OBJECT_PREFIX = ""

# A function to load CONFIG_DATA from file
def loadConfig():

    global CONFIG_DATA

    sys.stdout.write("\n")
    sys.stdout.write("Loading config data...")
    sys.stdout.write("\n")

    # If we have a stored config file, then use it, otherwise create an empty one
    if os.path.isfile(CONFIG_FILE):

        # Open the CONFIG_FILE and load it
        with open(CONFIG_FILE, 'r') as config_file:
            CONFIG_DATA = json.loads(config_file.read())

        sys.stdout.write("Config loading complete.")
        sys.stdout.write("\n")
        sys.stdout.write("\n")

    else:

        sys.stdout.write("Config file not found, loading empty defaults...")
        sys.stdout.write("\n")
        sys.stdout.write("\n")

        # Set the CONFIG_DATA defaults
        CONFIG_DATA = {
            "FMC_IP": "",
            "FMC_USER": "",
            "FMC_PASS": "",
            "IPv4_UUID": "",
            "IPv6_UUID": "",
            "AWS_SERVICES": "",
            "AWS_REGIONS": "",
            "SERVICE":  False,
            "SSL_VERIFY": False,
            "SSL_CERT": "/path/to/certificate",
            "AUTO_DEPLOY": False,
            "SYNC_TOKEN":  0
        }

# A function to store CONFIG_DATA to file
def saveConfig():

    sys.stdout.write("Saving config data...")
    sys.stdout.write("\n")

    with open(CONFIG_FILE, 'w') as output_file:
        json.dump(CONFIG_DATA, output_file, indent=4)

# A function to deploy pending policy pushes
def DeployPolicies(fmc):

    # Get pending deployments
    pending_deployments = fmc.getPendingDeployments()

    # Setup a dict to hold our deployments
    deployments = {}

    # See if there are pending deployments
    if pending_deployments['paging']['count'] > 0:

        # Iterate through pending deployments
        for item in pending_deployments['items']:

            # Only get ones that can be deployed
            if item['canBeDeployed']:

                # Only get ones that don't cause traffic interruption
                if item['trafficInterruption'] == "NO":

                    # If there are multiple devices, append them
                    if item['version'] in deployments:
                        device_list = deployments[item['version']]
                        device_list.append(item['device']['id'])
                        deployments[item['version']] = device_list
                    else:
                        deployments[item['version']] = [item['device']['id']]

        # Build JSON for each of our deployments
        for version, devices in deployments.items():

            deployment_json = {
                "type": "DeploymentRequest",
                "version": version,
                "forceDeploy": False,
                "ignoreWarning": True,
                "deviceList": devices,
            }

            fmc.postDeployments(deployment_json)

        sys.stdout.write("All pending deployments have been requested.\n")
    
    else:

        sys.stdout.write("There were zero pending deployments.\n")

# Function that can be used to schedule the O365WebServiceParser to refresh at intervals. Caution: this creates an infinite loop.
# Takes the O365WebServiceParser function and the interval as parameters. 
def intervalScheduler(function, interval):

    # user feedback
    sys.stdout.write("\n")
    sys.stdout.write(f"AWS Feed Parser will be refreshed every {interval} seconds. Please use ctrl-C to exit.\n")
    sys.stdout.write("\n")

    # interval loop, unless keyboard interrupt
    try:
        while True:
            function()
            # get current time, for user feedback
            date_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sys.stdout.write("\n")
            sys.stdout.write(f"{date_time} AWS Feed Parser executed by IntervalScheduler, current interval is {interval} seconds. Please use ctrl-C to exit.\n")
            sys.stdout.write("\n")
            # sleep for X amount of seconds and then run again. Caution: this creates an infinite loop to check the Web Service Feed for changes
            time.sleep(interval)

    # handle keyboard interrupt
    except (KeyboardInterrupt, SystemExit):
        sys.stdout.write("\n")
        sys.stdout.write("\n")
        sys.stdout.write("Exiting... AWS Feed Parser will not be automatically refreshed anymore.\n")
        sys.stdout.write("\n")
        sys.stdout.flush()
        pass

def check_for_new_version():

    # Get the latest version of the loaded feed
    sync_token_last = CONFIG_DATA['SYNC_TOKEN']

    # URL needed to check latest version
    aws_json_url = "https://ip-ranges.amazonaws.com/ip-ranges.json"

    # do GET request 
    response = requests.get(aws_json_url)

    #check if request was succesful
    if response.status_code == 200: 

        # grab output in JSON format
        AWS_JSON = json.loads(response.text)

        sync_token_new = int(AWS_JSON["syncToken"])
        sync_token_old = CONFIG_DATA['SYNC_TOKEN']

        if sync_token_old == 0:
            # user feedback
            sys.stdout.write(f"\nFirst time script runs, version of AWS {CONFIG_DATA['AWS_REGIONS']} commercial service instance endpoints detected: {sync_token_new}\n")
            # update version and save the config
            CONFIG_DATA['SYNC_TOKEN'] = sync_token_new
            saveConfig()
            return True,AWS_JSON
        else:
            # if the version did not change, the Web Service feed was not updated. 
            if(sync_token_new == sync_token_old):

                # user feed back
                sys.stdout.write("\nWeb Service List has NOT been updated since the last load, no update needed!\n\n") 
                
                return False,AWS_JSON

            # check if there is a newer version 
            if(sync_token_new > sync_token_old):

                # update version and save the config
                CONFIG_DATA['SYNC_TOKEN'] = sync_token_new
                saveConfig()

                # user feedback
                sys.stdout.write(f"\nNew version of AWS detected: {sync_token_new}\n")
                return True,AWS_JSON

    else:
        print(f"Sighting check request failed, status code: {response.status_code}\n")
    
# function to parse the Web Service, so that it can be called iteratively (e.g by the scheduler function)
def WebServiceParser():

    #check latest version
    bool_new_version,AWS_JSON = check_for_new_version()

    if bool_new_version == True:
        # Instantiate a Firepower object
        fmc = Firepower(CONFIG_DATA)

        # If there's no defined Network Object, make one, then store the UUID - else, get the current object
        if CONFIG_DATA['IPv4_UUID'] is '':

            # double checking that object name is not too large
            ipv4_name = OBJECT_PREFIX + "AWS_IPv4_" + '_'.join(CONFIG_DATA['AWS_SERVICES']) + "_" + '_'.join(CONFIG_DATA['AWS_REGIONS'])
            if len(ipv4_name) > 64:
                ipv4_name = OBJECT_PREFIX + "AWS_IPv4_NAME_TOO_LONG_RENAME_OBJECT_PLEASE"

            # Create the JSON to submit
            object_json = {
                'name': ipv4_name,
                'type': 'NetworkGroup',
                'overridable': True,
            }

            # Create the Network Group object in the FMC
            ipv4_group_object = fmc.createObject('networkgroups', object_json)

            # Save the UUID of the object
            CONFIG_DATA['IPv4_UUID'] = ipv4_group_object['id']
            saveConfig()
        else:
            # Get the Network Group object of the specified UUID
            ipv4_group_object = fmc.getObject('networkgroups', CONFIG_DATA['IPv4_UUID'])

        # If there's no defined Default Network Object, make one, then store the UUID - else, get the current object
        if CONFIG_DATA["IPv6_UUID"] is '':

            # double checking that object name is not too large
            ipv6_name = OBJECT_PREFIX + "AWS_IPv6_" + '_'.join(CONFIG_DATA['AWS_SERVICES']) + "_" + '_'.join(CONFIG_DATA['AWS_REGIONS'])
            if len(ipv6_name) > 64:
                ipv6_name = OBJECT_PREFIX + "AWS_IPv6_NAME_TOO_LONG_RENAME_OBJECT_PLEASE"

            # Create the JSON to submit
            object_json = {
                'name': ipv6_name,
                'type': 'NetworkGroup',
                'overridable': True,
            }

            # Create the Network Group object in the FMC
            ipv6_group_object = fmc.createObject('networkgroups', object_json)

            # Save the UUID of the object
            CONFIG_DATA['IPv6_UUID'] = ipv6_group_object['id']
            saveConfig()
        else:
            # Get the Network Group object of the specified UUID
            ipv6_group_object = fmc.getObject('networkgroups', CONFIG_DATA['IPv6_UUID'])

        # initiate lists to be filled with addresses
        IPv4_list = []
        IPv6_list = []

        # iterate through each 'item' in the JSON data
        for address in AWS_JSON["prefixes"]:
            if CONFIG_DATA['AWS_SERVICES'] == "ALL_SERVICES":
                if address["region"] in CONFIG_DATA['AWS_REGIONS']:
                    IPv4_list.append(address["ip_prefix"])
            else:
                if address["region"] in CONFIG_DATA['AWS_REGIONS'] and address["service"] in CONFIG_DATA['AWS_SERVICES']:
                    IPv4_list.append(address["ip_prefix"])
        
        # same for ipv6
        for address in AWS_JSON["ipv6_prefixes"]:
            if CONFIG_DATA['AWS_SERVICES'] == "ALL_SERVICES" and CONFIG_DATA['AWS_REGIONS'] == "ALL_REGIONS":
                IPv6_list.append(address["ipv6_prefix"])
            elif CONFIG_DATA['AWS_SERVICES'] == "ALL_SERVICES":
                if address["region"] in CONFIG_DATA['AWS_REGIONS']:
                    IPv6_list.append(address["ipv6_prefix"])
            elif CONFIG_DATA['AWS_REGIONS'] == "ALL_REGIONS":
                if address["service"] in CONFIG_DATA['AWS_REGIONS']:
                    IPv6_list.append(address["ipv6_prefix"])
            else:
                if address["region"] in CONFIG_DATA['AWS_REGIONS'] and address["service"] in CONFIG_DATA['AWS_SERVICES']:
                    IPv6_list.append(address["ipv6_prefix"])
            
        # Reset the fetched Network Group object to clear the 'literals'
        ipv4_group_object['literals'] = []
        ipv4_group_object.pop('links', None)

        # Add all the fetched IPs to the 'literals'of the Network Group object
        for ip_address in IPv4_list:
            ipv4_group_object['literals'].append({'type': 'Network', 'value': ip_address})

        # Update the NetworkGroup object
        fmc.updateObject('networkgroups', CONFIG_DATA['IPv4_UUID'], ipv4_group_object)

        # Reset the fetched Network Group object to clear the 'literals'
        ipv6_group_object['literals'] = []
        ipv6_group_object.pop('links', None)

         # Add all the fetched IPs to the 'literals'of the Network Group object
        for ip_address in IPv6_list:
            ipv6_group_object['literals'].append({'type': 'Network', 'value': ip_address})

        # Update the NetworkGroup object
        fmc.updateObject('networkgroups', CONFIG_DATA['IPv6_UUID'], ipv6_group_object)

        # user feed back
        sys.stdout.write("\n")
        sys.stdout.write(f"AWS IP addresses have been successfully updated for the {CONFIG_DATA['AWS_REGIONS']} plan and {CONFIG_DATA['AWS_SERVICES']} services!\n")
        sys.stdout.write("\n")

        saveConfig()

        # If the user wants us to deploy policies, then do it
        if CONFIG_DATA['AUTO_DEPLOY']:
            DeployPolicies(fmc)

    elif bool_new_version == False:
        # no new version, do nothing
        pass

##############END PARSE FUNCTION##############START EXECUTION SCRIPT##############

if __name__ == "__main__":

    # Load config data from file
    loadConfig()

    # If not hard coded, get the FMC IP, Username, and Password
    if CONFIG_DATA['FMC_IP'] == '':
        CONFIG_DATA['FMC_IP'] = input("FMC IP Address: ")
    if CONFIG_DATA['FMC_USER'] == '':
        CONFIG_DATA['FMC_USER'] = input("\nFMC Username: ")
    if CONFIG_DATA['FMC_PASS'] == '':
        CONFIG_DATA['FMC_PASS'] = getpass.getpass("\nFMC Password: ")
    # check with user which AWS service areas they are using
    if CONFIG_DATA['AWS_SERVICES'] == '':  
        answer_input = (input("\nDo you use all AWS Services (AMAZON, AMAZON_CONNECT, CLOUD9, CLOUDFRONT, CODEBUILD, DYNAMODB, EC2, EC2_INSTANCE_CONNECT, GLOBALACCELERATOR, ROUTE53, ROUTE53_HEALTHCHECKS, S3) [y/n]: ")).lower()
        if answer_input == "y":
            CONFIG_DATA['AWS_SERVICES'] = "ALL_SERVICES"
        elif answer_input == "n":
            aws_services = []
            if (input("\nDo you use AMAZON [y/n]: ")).lower() == "y":
                aws_services.append("AMAZON")
            if (input("\nDo you use AMAZON_CONNECT [y/n]: ")).lower() == "y":
                aws_services.append("AMAZON_CONNECT")
            if (input("\nDo you use CLOUD9 [y/n]: ")).lower() == "y":
                aws_services.append("CLOUD9")
            if (input("\nDo you use CLOUDFRONT [y/n]: ")).lower() == "y":
                aws_services.append("CLOUDFRONT")
            if (input("\nDo you use CODEBUILD [y/n]: ")).lower() == "y":
                aws_services.append("CODEBUILD")
            if (input("\nDo you use DYNAMODB [y/n]: ")).lower() == "y":
                aws_services.append("DYNAMODB")
            if (input("\nDo you use EC2 [y/n]: ")).lower() == "y":
                aws_services.append("EC2")
            if (input("\nDo you use EC2_INSTANCE_CONNECT [y/n]: ")).lower() == "y":
                aws_services.append("EC2_INSTANCE_CONNECT")
            if (input("\nDo you use GLOBALACCELERATOR [y/n]: ")).lower() == "y":
                aws_services.append("GLOBALACCELERATOR")
            if (input("\nDo you use ROUTE53 [y/n]: ")).lower() == "y":
                aws_services.append("ROUTE53")
            if (input("\nDo you use ROUTE53_HEALTHCHECKS [y/n]: ")).lower() == "y":
                aws_services.append("ROUTE53_HEALTHCHECKS")
            if (input("\nDo you use S3 [y/n]: ")).lower() == "y":
                aws_services.append("S3")
            CONFIG_DATA['AWS_SERVICES'] = aws_services
    # check with user which AWS region they are using
    if CONFIG_DATA['AWS_REGIONS'] is '':
        aws_regions_options = "ap-east-1, ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-south-1, ap-southeast-1, ap-southeast-2, ca-central-1, cn-north-1, cn-northwest-1, eu-central-1, eu-north-1, eu-west-1, eu-west-2, eu-west-3, me-south-1, sa-east-1, us-east-1, us-east-2, us-gov-east-1, us-gov-west-1, us-west-1, us-west-2, GLOBAL"
        aws_regions = []
        sys.stdout.write(f"\nAWS has the following regions: {aws_regions_options}.\n")
        aws_regions_input_string = input("\nPlease enter your region(s) in the EXACT spelling as displayed above.\nIf you have multiple regions, please comma seperate them without spaces: ")
        CONFIG_DATA['AWS_REGIONS'] = aws_regions_input_string.split(",")
        
    sys.stdout.write(f"\nChosen AWS regions: {CONFIG_DATA['AWS_REGIONS']}, chosen AWS services: {CONFIG_DATA['AWS_SERVICES']}\n")
    
    # Save the FMC data
    saveConfig()

    try:
        if CONFIG_DATA['SERVICE']:
            # Calls the intervalScheduler for automatic refreshing (pass O365WebServiceParser function and interval in seconds (1 hour = 3600 seconds))
            intervalScheduler(WebServiceParser, 3600) #set to 1 hour
        else:
            # Execute O365WebServiceParser just once
            WebServiceParser()

    except (KeyboardInterrupt, SystemExit):
        sys.stdout.write("\n\nExiting...\n\n")
        sys.stdout.flush()
        pass

# end of script

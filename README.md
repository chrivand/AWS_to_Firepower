# AWS_to_Firepower
This is a sample script that parses AWS IP addresses and creates Network Group Objects in Firepower Management Center. 

It is using the AWS public IP ranges, which are made public by [Amazon](https://aws.amazon.com/blogs/aws/aws-ip-ranges-json/). It parses the following link: https://ip-ranges.amazonaws.com/ip-ranges.json

After parsing the JSON feed, it creates 2 Network Group Objects, which can be used in Firepower Access or Pre-filter rules, Routing or other use cases.

Please contact me, Christopher Van Der Made <chrivand@cisco.com>, if you have any questions or remarks. If you find any bugs, please report them to me, and I will correct them (or do a pull request).

## Features

* Retrieving IPs from new AWS JSON feed; 
* Possibility to choose which AWS Regions and Services are needed;
* Creating right JSON format for FMC API PUT requests;
* Uploading this JSON to FMC, overwriting the previous Group Object;
* If no objects have been created (first time script runs), 2 overridable objects will be created: IPv4 and IPv6 separated;
* Checking if AWS JSON was updated (using the *syncToken*);
* Automatic policy deploy using API when changes were made to Objects (optional, caution this will also deploy other, unrelated policy changes);
* Continuously checking for updates with a specified time interval (optional).

## Solution Components

The script consists of 3 python files. The main script can run indefinitely (*AWS_json_parser.py*), leveraging a function that is built in, to rerun the script every x amount of seconds (it can also just be executed once). You can also use a cron job to do this. Then, using the *syncToken*, the script checks if changes were made to the AWS JSON feed. For full documentation of the AWS JSON feed, please review this link: https://docs.aws.amazon.com/general/latest/gr/aws-ip-ranges.html

### Cisco Products / Services

* Cisco Firepower Management Center;
* Cisco Firepower Threat Defense NGFW.

## Installation

These instructions will enable you to download the script and run it, so that the output can be used in Firepower as Group Objects. What do you need to get started? Please find a list of tasks below:

1. You need the IP address (or domain name) of the FMC, the username and password. These will be requested by the script the first time it is run. It is recommended to create a separate FMC login account for API usage, otherwise the admin will be logged out during every API calls. Add the IP/Domain of FMC, the username and password to the config_file.json file. If you do not add anything, you will be promted to fill this in when executing the script. 

2. The script will also prompt you for the Region you are using (ap-east-1, ap-northeast-1, etc.) and which Services (AMAZON, AMAZON_CONNECT, EC2, etc.) you are using. Potentially you can run this script multiple times to create separate objects per Service. Please make sure to create a separate directory with it's own version of the *config_file.json* file.

3. In the FMC, go to System > Configuration > REST API Preferences to make sure that the REST API is enabled on the FMC.

4. Two Network Group objects will be created automatically during the first run of the script. 

5. It is also recommended to download an SSL certificate from FMC and put it in the same folder as the scripts. This will be used to securely connect to FMC. In the **config_file.json file**, set the *"SSL_VERIFY"* parameter to *true*, and then set *"SSL_CERT"* to be the path to the FMC's certificate.

6. If you do not have the needed Python libraries set up, you will get an error when executing the script. You will need to install the *"requirements.txt"* file like this (make sure you are in the same directory as the cloned files live):

```
pip install -r requirements.txt
```

7. After this is complete you need to execute the script (make sure you are in the same directory as the cloned files live):

```
python3.6 AWS_json_parser.py
```

8. Optionally you can let this script run periodically, by setting *"SERVICE"* to *true* in the **config_file.json** file. In line 421 of the **AWS_json_parser.py** the time-period is set, per default it is set to an hour:

```
intervalScheduler(WebServiceParser, 3600) #set to 1 hour
```

11. Finally, if you want to automatically deploy the policies, you can set *"AUTO_DEPLOY"* to *true* in the **config.json** file. **Be very careful with this, as unfinished policies might be deployed by doing so.**

### Please take caution on the following notes:

* Please be aware that a policy redeploy is needed to update the Group Objects in the used Policies. Currently there is an optional API call built in to do a policy redeploy, however please take caution in using this, since this might cause other, unrelated policies or objects to be deployed (e.g., if another network administrator is working on a Policy in the GUI).

* Important is to use SSL verification and to test the script before running this in a production environment. In the config.json file, set the *"SSL_VERIFY"* parameter to *true*, and then set *"SSL_CERT"* to be the path to the FMC's certificate.

* Please test this properly before implementing in a production environment. This is a sample script.

* In case the intervalScheduler is used: the running script should be hosted in a secure environment! For example: if a malicious actor can place additional IP-addresses or URL's in the list somehow, they will be put in a Firepower trust rule, and might cause the malicious actor to bypass security.


## Author(s)

* Christopher van der Made (Cisco)
* Alan Nix (Cisco)
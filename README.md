# anyrun_to_misp

## Overview
This script stores the information analyzed by ANY.RUN in MISP.

It is possible to download MISP format files with the standard function of ANY.RUN. However, this file also contains a lot of non-IOC information.
Therefore, this script is based on the MISP format file that can be downloaded from ANY.RUN, but omits information that seems unnecessary for analysis. This will allow this script to focus on the IOC and reference information when registering with MISP.


## license

This software is released under the BSD License, see LICENSE.txt.


## Environment

* python3.6 or later
* Pymisp2.4.135.3 or later
* MISP2.4.135 or later


## Python module

* `pip3 install pymisp`
* `pip3 install requests`


## How to use


#### 1 API key confirmation of ANY.RUN

Please log in to ANY.RUN and check the API key of the account for which data is to be acquired.
The contents confirmed here will be used in the following items


#### 2 Setting the required constants

Open const.py and make the following settings


#### 2-1 ANY.RUN API key

Set the API key confirmed in "1 API key confirmation of ANY.RUN" to the following constant.

Target constant:
`ANYRUN_APIKEY`


#### 2-2 Storage location of downloaded files

The file downloaded from ANY.RUN is saved under the folder specified in the constant below.

Target constant:
`DOWNLOAD_DIRECTORY`

Download Files:

* Analysis history file: A file that contains download links for each file described below for each analysis result.
	* URL：https://api.any.run/v1/analysis/?skip=0
* MISP format file: A file in which analysis result information can be imported by MISP.
	* URL：https://api.any.run/report/analysis_id/summary/misp
* Summary file: A JSON file that contains a summary of the analysis results. This file is not currently used in this script, but is downloaded for reference.
	* URL：https://api.any.run/report/analysis_id/summary/json
* IOC file: A file in which only the IOC part is extracted from the analysis results
	* URL：https://api.any.run/report/analysis_id/ioc/json


#### 2-3 File to record the latest date of the registered event

Save the latest analysis date among the ANY.RUN analysis results that have completed MISP registration in the file defined by the following constants. At the next processing, only the analysis results newer than that date will be registered in MISP.

Target constant:
`EVENT_DATE_DAT`


#### 2-4 MISP settings

Set the registration destination MISP and the authentication key information of the user used for registration in the following constants.
In addition, the user set here needs permission to "add tag".

Target constant:

* URL of MISP
	* `MISP_URL`
* User authentication key
	* `MISP_AUTHKEY`


#### 2-5 Email settings

Email notification will be sent by defining each of the following constants.
If you don't need email notifications, set MAIL_TO to None.
For SMTP server information, please check your own available email account information.

Target constant:

* Email sender
	* `MAIL_FROM`
* Email destination
	* `MAIL_TO`
* Email subject
	* An email will be sent with the subject of the execution date and time concatenated with the character string set here.
	* `MAIL_SUBJECT`
* SMTP server connection destination
	* `MAIL_SMTP_SERVER`
* SMTP server username
	* `MAIL_SMTP_USER`
* SMTP server password
	* `MAIL_SMTP_PASSWORD`


#### 3 Script execution

It can be executed with the following command.

`python3 anyrun_to_misp.py`


## Remarks

* After executing the script, the event_date_dat file created in the same directory as the script is required for managing MISP imported data. In principle, do not operate.
* If the uuid of the event to be registered is already registered in MISP, the registration of that event will be skipped and the output "Event already exists" will be output. This does not affect the operation result.
* When importing MISP, the analysis result data downloaded from ANY.RUN may have tags that do not exist on MISP. In this case, add a new tag to MISP. Therefore, the user used for import needs "Add Tag" permission.
* When executing the first command, if there is a lot of registered data, an error may occur in the process. In that case, check if the event_date_dat file has been created. If it has been created, delete it and then execute the command again.
(Event registration is complete until the error occurs. Therefore, ignore them and register the uncaptured analysis results in MISP)


## Related item

* MISP project : http://www.misp-project.org/
* ANY.RUN : https://app.any.run/

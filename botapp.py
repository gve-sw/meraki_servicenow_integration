"""
Copyright (c) 2020 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""

from flask import Flask, request, jsonify
from webexteamssdk import WebexTeamsAPI
import json, os, requests

#get environment variables
WT_BOT_TOKEN = os.environ['WT_BOT_TOKEN']
WT_ROOM_ID = os.environ['WT_ROOM_ID']
MERAKI_SHARED_SECRET = os.environ['MERAKI_SHARED_SECRET']
SERVICENOW_INSTANCE = os.environ['SERVICENOW_INSTANCE']
SERVICENOW_USERNAME = os.environ['SERVICENOW_USERNAME']
SERVICENOW_PASSWORD = os.environ['SERVICENOW_PASSWORD']
SERVICENOW_INCIDENT_DEFAULT_IMPACT = os.environ['SERVICENOW_INCIDENT_DEFAULT_IMPACT']
SERVICENOW_INCIDENT_DEFAULT_URGENCY = os.environ['SERVICENOW_INCIDENT_DEFAULT_URGENCY']

#start Flask and WT connection
app = Flask(__name__)
api = WebexTeamsAPI(access_token=WT_BOT_TOKEN)

# defining the decorater and route registration for incoming meraki alerts
@app.route('/', methods=['POST'])
def meraki_alert_received():
    # get full Meraki alert log
    meraki_raw_json = request.get_json()

    # verify shared secret
    meraki_sharedSecret = meraki_raw_json["sharedSecret"]
    if meraki_sharedSecret == MERAKI_SHARED_SECRET:
        pass
    else:
        print("Shared secret does not match.")
        return jsonify({'success': True})

    # retrieve specific Meraki alert data
    meraki_organizationName = meraki_raw_json["organizationName"]
    meraki_networkName = meraki_raw_json["networkName"]
    meraki_alertType = meraki_raw_json["alertType"]
    meraki_occuredAt_date = meraki_raw_json["occurredAt"][:10]
    meraki_occuredAt_time = meraki_raw_json["occurredAt"][11:19]
    meraki_alertId = meraki_raw_json["alertId"]

    # notify the user about alert and incident creation
    if meraki_alertId:
        notification_alert = (
            f"🚨 **Alert in Meraki (ID: {meraki_alertId})** 🚨  \n"
            f"🔔 *{meraki_alertType}* at {meraki_occuredAt_time} on {meraki_occuredAt_date} in the *{meraki_networkName}* network (*{meraki_organizationName}* organization)  \n"
            f"📝 An incident is being created in ServiceNow."
        )
    else: # in case the alertId field is empty, e.g. when the webhook test API is used
        notification_alert = (
            f"🚨 **Alert in Meraki** 🚨  \n"
            f"🔔 *{meraki_alertType}* at {meraki_occuredAt_time} on {meraki_occuredAt_date} in the *{meraki_networkName}* network (*{meraki_organizationName}* organization), no alert ID available  \n"
            f"📝 An incident is being created in ServiceNow."
        )
    api.messages.create(roomId=WT_ROOM_ID, markdown=notification_alert)

    # create incident in ServiceNow
    headers = {"Content-Type":"application/json", "Accept":"application/json"}
    auth = (SERVICENOW_USERNAME, SERVICENOW_PASSWORD)
    servicenow_caller = requests.get(SERVICENOW_INSTANCE + "/api/now/table/sys_user?sysparm_query=user_name%3D" + SERVICENOW_USERNAME, auth=auth, headers=headers).json()['result'][0]['name']
    if meraki_alertId:
        ticket = {
            "caller_id": servicenow_caller,
            "impact": SERVICENOW_INCIDENT_DEFAULT_IMPACT,
            "urgency": SERVICENOW_INCIDENT_DEFAULT_URGENCY,
            "category": "Network",
            "short_description": meraki_alertType + " (Alert ID: " + meraki_alertId  + ")",
            "description": "The full Meraki log for this alert is:  \n" + json.dumps(meraki_raw_json, indent=4)
        }
    else:
        ticket = {
            "caller_id": servicenow_caller,
            "impact": SERVICENOW_INCIDENT_DEFAULT_IMPACT,
            "urgency": SERVICENOW_INCIDENT_DEFAULT_URGENCY,
            "category": "Network",
            "short_description": meraki_alertType + " (No Alert ID available)",
            "description": "The full Meraki log for this alert is:  \n" + json.dumps(meraki_raw_json, indent=4)
        }
    ticket_creation = requests.post(SERVICENOW_INSTANCE + "/api/now/table/incident", auth=auth, headers=headers, json=ticket)

    # get incident information from response body
    servicenow_raw_json = ticket_creation.json()
    servicenow_ticket_number = servicenow_raw_json["result"]["number"]
    servicenow_ticket_opened_at_date = servicenow_raw_json["result"]["opened_at"][:10]
    servicenow_ticket_opened_at_time = servicenow_raw_json["result"]["opened_at"][11:]
    servicenow_ticket_sys_id = servicenow_raw_json["result"]["sys_id"]
    servicenow_priority = servicenow_raw_json["result"]["priority"]
    servicenow_incident_url = SERVICENOW_INSTANCE + "/incident.do?sys_id=" + servicenow_ticket_sys_id

    # update users with incident information
    if meraki_alertId:
        notification_ticket_created = (
            f"📂 A **ServiceNow incident** for the Meraki alert *{meraki_alertId}* (Alert: *{meraki_alertType}*) has been created at {servicenow_ticket_opened_at_time} on {servicenow_ticket_opened_at_date}.  \n"
            f"The incident number is **{servicenow_ticket_number}** and the priority is set to {servicenow_priority} by default.  \n"
            f"[**Click here**]({servicenow_incident_url}) for more information or to make changes to the incident."
        )
    else: # in case the alertId field is empty, e.g. when the webhook test API is used
        notification_ticket_created = (
            f"📂 A **ServiceNow incident** for the Meraki alert at {meraki_occuredAt_time} on {meraki_occuredAt_date} (Alert: *{meraki_alertType}*) has been created at {servicenow_ticket_opened_at_time} on {servicenow_ticket_opened_at_date}.  \n"
            f"The incident number is **{servicenow_ticket_number}** and the priority is set to {servicenow_priority} by default.  \n"
            f"[**Click here**]({servicenow_incident_url}) for more information or to make changes to the incident."
        )
    api.messages.create(roomId=WT_ROOM_ID, markdown=notification_ticket_created)

    return jsonify({'success': True})

if __name__=="__main__":
    app.run()
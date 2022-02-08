#####
#
# Python integration script to create tickets in Jira using EC2 recommendations from Cloudability.
# This workaround bridges the gap for ticket creation to Jira Server / Data Center (sunsetting in 1st Feb 2024)
#
#
# This script has been tested with Jira Server v8.21.1
#
# 8th Feb 2022 - v0.2
####
import requests
import json
from requests.auth import HTTPBasicAuth

def aws_accounts():
    cldy_vendor_credential_url = "https://api.cloudability.com/v3/vendors/AWS/accounts"
    headers = {"Accept": "application/json"}
    auth = HTTPBasicAuth(cldy_api_key, '')
    cldy_vendor_credential_response = requests.get(cldy_vendor_credential_url,headers=headers, auth=auth)
    cldy_accounts_list = json.loads(cldy_vendor_credential_response.text)
    for result in cldy_accounts_list['result']:
        cldy_accounts_dict[result['vendorAccountId']] = result['vendorAccountName']

def cldy_ec2_rightsizing():
    url = 'https://api.cloudability.com/v3/rightsizing/aws/recommendations/ec2'
    cldy_payload = {"basis": "effective", 
            "limit": 10,
           "maxRecsPerResource": 1,
           "rank": "default",
           "sort": "-recommendations.savings",
           "offset": 0,
           "duration": "thirty-day",
           "filters": "recommendations.savings > 1000"}

    headers = {"Accept": "application/json"}

    auth = HTTPBasicAuth(cldy_api_key, '')
    response = requests.get(url, params=cldy_payload, headers=headers, auth=auth)
    rsJSON = response.json()
    return rsJSON

def create_jira_ticket():
    jira_ticket_summary = f"Apptio Cloudability Recommendations: {action} AWS EC2 Resource ID {resourceId} (Account Name: {accountname}) from {currentNodeType} to {recommendedNodeType} to achieve 30-days cost savings of ${str(savings)} ({str(percentagesavings)}%)."
    print(jira_ticket_summary)

    # Initialize connection for Jira
    jira_url ="http://localhost:8080/rest/api/2/issue/"

    jira_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    jira_authentication_email = "replace_with_jira_service_account_name_excludes_domain_name"
    jira_api_token = "replace_with_jira_service_account_password"
    jira_auth = HTTPBasicAuth(jira_authentication_email, jira_api_token)

    # Amend Jira ticket details specific to your environment e.g. custom fields, ticket issue types, description, summary
    jira_payload = json.dumps( 
        { "fields": 
            {
                "project":
                {
                    "key": "CLOUD"
                },
                "summary": jira_ticket_summary,
                "description": ticket_description,
                "issuetype": {
                    "name": "Change"
            }
        }
    })

    response = requests.request(
    "POST",
    jira_url,
    data=jira_payload,
    headers=jira_headers,
    auth=jira_auth
    )

    print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))

# Main Program:
# Use function to do the following:
# (1)    [aws_account function] Load accounts list from cldy into a dictionary "cldy_accounts_list" and 
#        load the key value of accountID / AccountName into another dictionary "cldy_accounts_dict"
# (2)    [cldy_ec2_rightsizing function] Load EC2 rightsizing recommendations and process them in the main body
# (2.1)  As part of the main body, initiate creation of tickets in [create_jira_ticket function]
#
cldy_api_key = 'replace_with_your_unique_cldy_api_key'

cldy_accounts_dict = {}
aws_accounts()
rsJSON = cldy_ec2_rightsizing()

for result in rsJSON['result']:
    resourceId = result['resourceIdentifier']

    name = result['name']

    accountID = result['vendorAccountId']
    accountname = cldy_accounts_dict[accountID]
    tagkey = result['tagMappings'][0]['tagName']
    tagvalue = result['tagMappings'][0]['vendorTagValue']
    action = result['recommendations'][0]['action']
    savings = result['recommendations'][0]['savings']
    percentagesavings = result['recommendations'][0]['savingsPct']
    
    currentNodeType = result['nodeType']
    recommendedNodeType = result['recommendations'][0]['nodeType']
    nodeOS = result['os'] 
    currentspend = result['totalSpend']
    optimizedspend = round(currentspend - savings,2)
    
    ticket_description = f"*Details of Recommendations*\r\n\r\nService Name: AWS EC2\r\n\r\nResource Name: {name}\r\n\r\nResource ID: {resourceId}\r\n\r\nAccount ID: {accountID}\r\n\r\nAccount Name: {accountname}\r\n\r\nRecommended Action: {action}\r\n\r\nCurrent Instance Size: {currentNodeType}\r\n\r\nRecommended Instance Size: {recommendedNodeType}\r\n\r\nOperating System: {nodeOS}\r\n\r\n\r\n----\r\n*Financial Summary*\r\n\r\nCost before recommendation: ${currentspend}\r\n\r\nCost after recommendation: ${optimizedspend}\r\n\r\nCost saving amount: ${savings}\r\n\r\nCost saving percentage: {percentagesavings}%\r\n\r\n----\r\n*Resource Tags Summary*\r\n\r\n"

    # To parse all the tag key and values
    for tag_result in result['tagMappings']:
        tagkey = tag_result['tagName']
        tagvalue = tag_result['vendorTagValue']

        ticket_description = ticket_description + f"{tagkey}: {tagvalue}\r\n\r\n"

    # Initiate function to create Jira tickets
    create_jira_ticket()
#####
#
# Python integration script to create tickets in Jira using EC2 recommendations from Cloudability.
# This workaround bridges the gap for ticket creation to Jira Server / Data Center (sunsetting in 1st Feb 2024)
#
#
# This script has been tested with Jira Server v8.21.1
#
# 11th Feb 2022 - v0.3 Supports reference to one business mappings
#
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

def cldy_business_mappings():
    # Replace index to the desired Business dimension for your environment
    cldy_business_dimension_index = '3'
    cldy_biz_dimension_url = f"https://api.cloudability.com/v3/business-mappings/{cldy_business_dimension_index}"
    
    headers = {"Accept": "application/json"}
    auth = HTTPBasicAuth(cldy_api_key, '')
    
    # Get business dimension from Cloudability API
    cldy_biz_dimension_response = requests.get(cldy_biz_dimension_url,headers=headers, auth=auth)

    # Convert data to dict
    cldy_biz_dimension_json = json.loads(cldy_biz_dimension_response.text)
    
    # Convert dict to string for purpose of data cleansing
    cldy_biz_dimension_str = json.dumps(cldy_biz_dimension_json)

    cleansed_str_1 = cldy_biz_dimension_str.replace("TAG['Role'] == ","")
    cleansed_str_2 = cleansed_str_1.replace("'","")

    # Convert string to dict
    cldy_biz_dimension_json_cleansed = json.loads(cleansed_str_2)
    result_of_level1_dict = cldy_biz_dimension_json_cleansed['result']
    result_of_statement_list = result_of_level1_dict['statements']
    
    # Put list of key and value from the "statement" element
    for tagvalue_bm_dimension_result in result_of_level1_dict['statements']:
        cldy_biz_dimension_dict[tagvalue_bm_dimension_result['matchExpression']] = tagvalue_bm_dimension_result['valueExpression']
        #
        # [Troubleshooting] Statements below to test elements in "statements"
        #
        # tagvalue = tagvalue_bm_dimension_result['matchExpression']
        # bm_dimension = tagvalue_bm_dimension_result['valueExpression']
        # print(tagvalue, bm_dimension)

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

    # Initialize connection for Jira. Replace this to your server URL
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
                "customfield_10200": savings,
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

# Global Variable Initialization
cldy_api_key = 'replace this with your cldy api key'

# Initialize dictionaries to store key value of
#  - accountsID to accountName 
#  - Tag to Cost Center
cldy_accounts_dict = {}
cldy_biz_dimension_dict = {} 

# Main Program:
# Use function to do the following:
# (1)      [aws_account function] Load accounts list from cldy into a dictionary "cldy_accounts_list" and 
#          load the key value of accountID / AccountName into another dictionary "cldy_accounts_dict"
# (2)      [cldy_business_mappings function] Uses the resource mapping in business mapping to contextualize spend to an organization domain 
#          Cloudability can serve as the single source of truth. Apart from being informative, it is hopeful that this can be used to automate ticket
#          assignee 
# (3)      [cldy_ec2_rightsizing function] Load EC2 rightsizing recommendations and process them in the main body
# (3.1)    As part of the main body, 
# (3.1.1)   - curate ticket description
# (3.1.2)   - initiate creation of tickets in [create_jira_ticket function]
#
aws_accounts()
cldy_business_mappings()

rsJSON = cldy_ec2_rightsizing()

for result in rsJSON['result']:
    resourceId = result['resourceIdentifier']

    name = result['name']

    accountID = result['vendorAccountId']
    accountname = cldy_accounts_dict[accountID]

    # To parse all the tag key and values
    tag_dictionary = {}
    for tag_returns in result['tagMappings']:
        tag_dictionary[tag_returns['tagName']] = tag_returns['vendorTagValue']
        tagkey = tag_returns['tagName']
        tagvalue = tag_returns['vendorTagValue']
        
        # curate strings to be appended in ticket description
        tag_for_description = f"{tagkey}: {tagvalue}\r\n\r\n"

    # Uncomment to identify tag key / value to use for Business Mapping reference
    # print(tag_dictionary)

    # 
    # Cloudability business mapping can serve as the source of record to contextualize spend in the organization
    # The next few statements will provide a lookup to one business mapping dimension in the function cldy_business_mapping in cldy_business_map.py 
    # For this code, there is a business mapping that maps tags to cost center. It therefore looks up cost center name using a tag value.
    # 
    # Replace this based on the tag key of interest. Use the above print(tag_dictionary) to identify the particular tag of interest
    tag_of_interest = tag_dictionary['Role']
    
    team_name = cldy_biz_dimension_dict[tag_of_interest]

    action = result['recommendations'][0]['action']
    savings = result['recommendations'][0]['savings']
    percentagesavings = result['recommendations'][0]['savingsPct']
    
    currentNodeType = result['nodeType']
    recommendedNodeType = result['recommendations'][0]['nodeType']
    nodeOS = result['os'] 
    currentspend = result['totalSpend']
    optimizedspend = round(currentspend - savings,2)
    
    # Replace this string to your preferred string 
    ticket_description = f"*Details of Recommendations*\r\n\r\nService Name: AWS EC2\r\n\r\nTeam Name: {team_name}\r\n\r\nResource Name: {name}\r\n\r\nResource ID: {resourceId}\r\n\r\nAccount ID: {accountID}\r\n\r\nAccount Name: {accountname}\r\n\r\nRecommended Action: {action}\r\n\r\nCurrent Instance Size: {currentNodeType}\r\n\r\nRecommended Instance Size: {recommendedNodeType}\r\n\r\nOperating System: {nodeOS}\r\n\r\n\r\n----\r\n*Financial Summary*\r\n\r\nCost before recommendation: ${currentspend}\r\n\r\nCost after recommendation: ${optimizedspend}\r\n\r\nCost saving amount: ${savings}\r\n\r\nCost saving percentage: {percentagesavings}%\r\n\r\n----\r\n*Resource Tags Summary*\r\n\r\n{tag_for_description}"
    # print(ticket_description)

    # Initiate function to create Jira tickets
    create_jira_ticket()

import boto3
from botocore.exceptions import ClientError

import json
import os
import time
import datetime
from dateutil import tz

from lib.account import *
from lib.common import *

import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)

RESOURCE_PATH = "cloudtrail"

def lambda_handler(event, context):
    logger.debug("Received event: " + json.dumps(event, sort_keys=True))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Received message: " + json.dumps(message, sort_keys=True))

    try:
        target_account = AWSAccount(message['account_id'])
        for r in target_account.get_regions():
            discover_trails(target_account, r)


    except AssumeRoleError as e:
        logger.error("Unable to assume role into account {}({})".format(target_account.account_name, target_account.account_id))
        return()
    except ClientError as e:
        logger.error("AWS Error getting info for {}: {}".format(target_account.account_name, e))
        return()
    except Exception as e:
        logger.error("{}\nMessage: {}\nContext: {}".format(e, message, vars(context)))
        raise

def discover_trails(target_account, region):
    '''Iterate across all regions to discover CloudTrails'''

    ct_client = target_account.get_client('cloudtrail', region=region)
    response = ct_client.describe_vpcs()

    for trail in response['trailList']:

        # CloudTrail will return trails from other regions if that trail is collecting events from the region where the api call was made
        if region != trail['TrailARN'].split(":")[3]:
            # Move along if the region of the trail is not the region we're making the call to
            continue

        resource_name = "{}-{}-{}".format(account.account_id, region, trail['Name'])

        event_response = ct_client.get_event_selectors(TrailName=trail['Name'])
        trail['EventSelectors'] = event_response['EventSelectors']

        status_response = ct_client.get_trail_status(Name=trail['Name'])
        trail['Status'] = status_response

        # tag_response = ct_client.list_tags(ResourceIdList=[ trail['TrailARN'] ] )

        # Save all Trails!
        trail['resource_type']    = "cloudtrail"
        trail['account_id']       = target_account.account_id
        trail['account_name']     = target_account.account_name
        save_resource_to_s3(RESOURCE_PATH, resource_name, trail)



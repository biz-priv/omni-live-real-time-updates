import os
import sys
import pandas as pd
import boto3

cur_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(cur_dir)
shared_dir = os.path.join(src_dir, 'shared')

sys.path.insert(0, shared_dir)

from utils import write_sns_to_dynamodb

def handler(event, context):
    try:
        # Log the incoming event
        print("Event received:", event)
        # Pass a default value for msg_att_name for testing
        write_sns_to_dynamodb(event, os.environ['SNS_TOPIC_ARN'], os.environ['DYNAMO_DB_TABLE'], msg_att_name='id')
    except Exception as e:
        print("Error processing live stops table:", e)
        raise Exception("Error processing live stops table: ") from e


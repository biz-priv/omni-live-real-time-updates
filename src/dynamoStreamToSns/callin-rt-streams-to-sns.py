import pandas as pd
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(cur_dir)
shared_dir = os.path.join(src_dir, 'shared')

sys.path.insert(0, shared_dir)

from utils import write_sns_to_dynamodb

def handler(event, context):
    try:
        write_sns_to_dynamodb(event, os.environ['SNS_TOPIC_ARN'], os.environ['DYNAMO_DB_TABLE'])
    except Exception as e:
        print("Error processing live callin table:", e)
        raise Exception("Error processing live callin table: ") from e
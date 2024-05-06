import pandas as pd
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(cur_dir)
shared_dir = os.path.join(src_dir, 'shared')

sys.path.insert(0, shared_dir)

from utils import getFileFromS3, write_df_to_dynamodb


def handler(event, context):
    try:
        print(event)
        records = event.get('Records')[0]
        s3Key = records['s3']['object']['key']
        bucket = 'dms-dw-etl-lvlp'
        df = getFileFromS3(bucket, s3Key)

        df_sorted = df.sort_values(by=['id', 'transact_id'], ascending = [True, False])

        df_unique = df_sorted.drop_duplicates(subset='id', keep='first')
        
        print(df_sorted[['id', 'transact_id']])
        print(df_unique[['id', 'transact_id']])
        
        write_df_to_dynamodb(df_unique, 'omni-live-orders-dev')
        print("Completed")

    except Exception as e:
        print("Error processing live orders:", e)
        raise Exception("Error processing live orders: ") from e
        
    
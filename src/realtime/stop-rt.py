import pandas as pd
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(cur_dir)
shared_dir = os.path.join(src_dir, 'shared')

sys.path.insert(0, shared_dir)

from utils import getFileFromS3, write_df_to_dynamodb, write_to_dynamo, get_transact_ids


def handler(event, context):
    try:
        print(event)
        records = event.get('Records')
        for record in records:
            s3Key = record['s3']['object']['key']
            bucket = os.environ['S3_BUCKET']
            df = getFileFromS3(bucket, s3Key)
            df_sorted = df.sort_values(by=['id', 'transact_id'], ascending = [True, True])
            # df_unique = df_sorted.drop_duplicates(subset='id', keep='first')
            print(df_sorted[['id', 'transact_id']])
            # print(df_unique[['id', 'transact_id']])
            unique_ids = get_transact_ids(df_sorted, os.environ['LIVE_STOPS_DB'])
            write_to_dynamo(df_sorted, os.environ['LIVE_STOPS_DB'], unique_ids)
            # write_df_to_dynamodb(df_unique, os.environ['LIVE_STOPS_DB'])

        print("Completed")

    except Exception as e:
        print("Error processing live stops table:", e)
        raise Exception("Error processing live stops table: ") from e
        
    
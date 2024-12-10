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
            print(df_sorted[['id', 'transact_id']])
            unique_ids = get_transact_ids(df_sorted, os.environ['LIVE_OTHER_CHARGE_DB'])
            write_to_dynamo(df_sorted, os.environ['LIVE_OTHER_CHARGE_DB'], unique_ids)

        print("Completed")

    except Exception as e:
        print("Error processing other charge-table:", e)
        raise Exception("Error processing live other-charge table: ") from e
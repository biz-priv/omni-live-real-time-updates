import boto3
import pandas as pd
import json
import io


def getFileFromS3(bucketName, s3key):
    try: 
        s3Client = boto3.client('s3')
        s3Obj = s3Client.get_object(Bucket=bucketName, Key=s3key)
        buffer = io.BytesIO(s3Obj['Body'].read())
        df_orders = pd.read_parquet(buffer, engine='pyarrow')
        return df_orders

    except Exception as e:
        print("Error in getFileFromS3: ", e)
        raise Exception("Error getting query from S3: ") from e
        
def _convert_value(val):
    """ Convert Python data types to DynamoDB-compatible types. """
    if isinstance(val, str):
        return val
    elif isinstance(val, int) or isinstance(val, float):
        return str(val)
    elif isinstance(val, bool):
        return val
    elif isinstance(val, list):  # Lists of strings or numbers
        return val
    elif isinstance(val, dict):  # Nested dictionaries
        return val
    else:
        return val
        
def write_df_to_dynamodb(df, table_name):
    try:
        table = boto3.resource('dynamodb', region_name='us-east-1').Table(table_name)
        items = df.apply(lambda x: json.loads(x.to_json()), axis=1)
        for item in items:
            dynamo_item = {k: _convert_value(v) for k, v in item.items()}
            response = table.put_item(Item=dynamo_item)
            print("Successfully inserted item:", dynamo_item)
    except Exception as e:
        print("write_df_to_dynamodb(): Error inserting item:", e)
        raise Exception("Error inserting item: ") from e

        
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
        
    
import boto3
import pandas as pd
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
        
def handler(event, context):
    print("hello")
    print(event)
    records = event.get('Records')[0]
    s3Key = records['s3']['object']['key']
    bucket = 'dms-dw-etl-lvlp'
    df = getFileFromS3(bucket, s3Key)

    df_sorted = df.sort_values(by=['id', 'transact_id'], ascending = [True, False])

    df_unique = df_sorted.drop_duplicates(subset='id', keep='first')

    print(df_unique[['id', 'transact_id', 'blnum']])
import boto3
import pandas


def getFileFromS3(bucketName, s3key):
    try: 
        # parts = s3key.split("/")
        # directories = parts[:-1]
        # filename = parts[-1] 
        s3Client = boto3.client('s3')
        s3Obj = s3Client.get_object(Bucket=bucketName, Key=s3key)
        df_orders = pandas.read_parquet(s3Obj, engine='pyarrow')
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
    ordersFile = getFileFromS3(bucket, s3Key)
    
    print(ordersFile)
    
    
    
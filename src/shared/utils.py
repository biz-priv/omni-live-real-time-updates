import boto3
import pandas as pd
import json
import io
import os
import datetime
import pytz
import uuid
dynamodb = boto3.resource('dynamodb')


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
        table = boto3.resource('dynamodb', region_name=os.environ['REGION']).Table(table_name)
        items = df.apply(lambda x: json.loads(x.to_json()), axis=1)
        for item in items:
            dynamo_item = {k: _convert_value(v) for k, v in item.items()}
            response = table.put_item(Item=dynamo_item)
            print("Successfully inserted item:", dynamo_item)
            failed_list(item,table_name)
    except Exception as e:
        print("write_df_t(o_dynamodb(): Error inserting item:", e)
        failed_list(item,table_name)
        raise Exception("Error inserting item: ") from e
    
   

def failed_list(item,table_name,e):
    try:
        table = dynamodb.Table(os.environ['FAILED_RECORDS'])
        item = {
            'UUid': uuid.uuid4(),
            'Sourcetable': table_name,
            'FailedRecord': item,
            'Status': "INSERTED",
            'ErrorMessage': e,
            'Timestamp': datetime.now(pytz.utc)
        }
        table.put_item(Item=item)
        print("Failed record has been reprocessed:", item)
    except Exception as e:
        print("Error adding failed record to DynamoDB:", str(e))


# In utils.py

def write_sns_to_dynamodb(event, topic_arn, table_name, msg_att_name=None):
    sns_client = boto3.client('sns')
    try:
        # Log the records from the event
        records = event.get('Records', None)
        print("Records:", records)

        if records is None:
            raise ValueError("Event does not contain 'Records' key or it is None")
        
        for element in records:
            print("Processing element:", element)
            try:
                if msg_att_name:
                    new_image = element.get('dynamodb', {}).get('NewImage', {})
                    print("New Image:", new_image)
                    
                    if not new_image:
                        print("No NewImage found in the record")
                        continue
                    
                    if msg_att_name in new_image:
                        msg_att_value = new_image[msg_att_name].get('S')
                        print("msgAttValue:", msg_att_value)
                        
                        if msg_att_value:
                            message_attributes = {
                                msg_att_name: {
                                    'DataType': 'String',
                                    'StringValue': str(msg_att_value),
                                },
                            }
                            print("messageAttributes:", message_attributes)
                            sns_publish(sns_client, element, topic_arn, table_name, message_attributes)
                        else:
                            print("msg_att_value is empty or None")
                    else:
                        print(f"{msg_att_name} not found in NewImage")
            except Exception as error:
                print("Error processing element:", error)
        return "Success"
    except Exception as error:
        print("Error in write_sns_to_dynamodb:", error)
        return "Process failed"



def sns_publish(sns_client, element, topic_arn, table_name, message_attributes):
    try:
        print("SNS Publish")
        dynamo_item = element.get('dynamodb', {}).get('NewImage', {})
        if dynamo_item:
            dynamo_item = json.loads(json.dumps(dynamo_item, default=str))
            dynamo_item['tableName'] = table_name
            print("Dynamo Item to Publish:", dynamo_item)
            sns_client.publish(
                TopicArn=topic_arn,
                Message=json.dumps(dynamo_item),
                MessageAttributes=message_attributes
            )
            print("SNS Publish successful")
        else:
            print("No DynamoDB item found.")
    except Exception as e:
        print("Error in sns_publish:", e)
        raise Exception("Error publishing to SNS: ") from e

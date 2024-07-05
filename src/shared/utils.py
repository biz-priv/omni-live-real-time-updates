import boto3
import pandas as pd
import json
import io
import os


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
    except Exception as e:
        print("write_df_to_dynamodb(): Error inserting item:", e)
        raise Exception("Error inserting item: ") from e
    
def write_sns_to_dynamo(event, topic_arn, table_name, msg_att_name=None):
    sns_client = boto3.client('sns')
    try:
        records = event['Records']
        message_attributes = None
        for element in records:
            try:
                if msg_att_name:
                    new_image = element.get('dynamodb', {}).get('NewImage', {})
                    if new_image and msg_att_name in new_image:
                        msg_att_value = new_image[msg_att_name]['S'] if 'S' in new_image[msg_att_name] else None
                        print("msgAttValue", msg_att_value)
                        if msg_att_value == "" or msg_att_value is None:
                            message_attributes = None
                        else:
                            message_attributes = {
                                msg_att_name: {
                                    'DataType': 'String',
                                    'StringValue': str(msg_att_value),
                                },
                            }
                        print("messageAttributes", message_attributes)
                        sns_publish(sns_client, element, topic_arn, table_name, message_attributes)
                # if element['eventName'] == 'REMOVE' and 'omni-live-rt-replication-movement-Order-rt-ddb-to-sns' in topic_arn:
                #     print("Dynamo REMOVE event")
                #     sns_publish(sns_client, element, topic_arn, table_name, message_attributes)
                #     continue
                # if element['eventName'] == 'REMOVE':
                #     print("Dynamo REMOVE event")
                #     continue
                # sns_publish(sns_client, element, topic_arn, table_name, message_attributes)
            except Exception as error:
                print("error:forloop", error)
        return "Success"
    except Exception as error:
        print("error", error)
        return "process failed"
    

def sns_publish(sns_client, element, topic_arn, table_name, message_attributes):
    try:
        print("SNS Publish")
        dynamo_item = element.get('dynamodb', {}).get('NewImage', {})
        if dynamo_item:
            dynamo_item = json.loads(dynamo_item.to_json())
            dynamo_item['tableName'] = table_name
            sns_client.publish(
                TopicArn=topic_arn,
                Message=json.dumps(dynamo_item),
                MessageAttributes=message_attributes
            )
        else:
            print("No DynamoDB item found.")
    except Exception as e:
        print("Error in sns_publish: ", e)
        raise Exception("Error publishing to SNS: ") from e

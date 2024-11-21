import boto3
import pandas as pd
import json
import io
import os
import datetime
import pytz
import uuid
from datetime import datetime
from boto3.dynamodb.conditions import Key
dynamodb = boto3.resource('dynamodb')
sns_client = boto3.client('sns')

def query_dynamo_and_get_transact_id(table_name, key, value):
    # Select the table
    table = dynamodb.Table(table_name)
    
    try:
        # Query the table
        response = table.query(
            KeyConditionExpression=Key(key).eq(value)
        )
        
        if response['Items']:
            transact_id = response['Items'][0].get('transact_id', 0)  # Default to 0 if not found
            return int(transact_id) if str(transact_id).isdigit() else 0
        else:
            print(f"No item found with id {value}")
            return 0
    
    except Exception as e:
        print(f"Error querying DynamoDB: {e}")
        raise Exception("Error querying DynamoDB:") from e

def get_transact_ids(df, table_name):
    
    id_dict = {}
    unique_ids = df['id'].unique()

    for id in unique_ids:
        try:
            transact_id = query_dynamo_and_get_transact_id(table_name, 'id', id)
            id_dict[id] = transact_id

        except Exception as e: 
            print(f"[ERROR] Error processing id {id}: {e}")
            raise Exception(f"Error processing id {id}: {e}") from e

    return id_dict
    

def write_to_dynamo(df, table_name, id_dict):
    try:
        table = boto3.resource('dynamodb', region_name=os.environ['REGION']).Table(table_name)
        
        # get cst timezone
        cst = pytz.timezone('America/Chicago')

        # Convert DataFrame rows to dictionary
        items = df.apply(lambda x: json.loads(x.to_json()), axis=1)
        
        for item in items:
            row_id = item['id']
            
            # Handle cases where transact_id might be empty or None
            row_transact_id = item.get('transact_id')
            
            # Add timestamp
            item['inserted_timestamp'] = datetime.now(cst).isoformat()

            # Prepare DynamoDB item
            dynamo_item = {k: _convert_value(v) for k, v in item.items()}

            # Logic for insertion based on transact_id
            if row_id in id_dict:
                # If transact_id is None or empty, skip comparison
                if row_transact_id is None or row_transact_id == '':
                    response = table.put_item(Item=dynamo_item)
                    print(f"Inserted item with empty transact_id for id {row_id}")
                # If transact_id has a value, compare with existing
                elif row_transact_id and int(row_transact_id) > id_dict[row_id]:
                    response = table.put_item(Item=dynamo_item)
                    print(f"Successfully inserted item with higher transact_id for id {row_id}")
                else:
                    print(f"{row_id} is already present with a higher or equal transact_id, skipping this")
            else:
                # If the id doesn't exist in the table, insert unconditionally
                response = table.put_item(Item=dynamo_item)
                print(f"Successfully inserted new item for id {row_id}")

    except Exception as e:
        print("write_to_dynamo(): Error inserting item:", e)
        failed_list(item, table_name, e)
        raise Exception("Error inserting item: ") from e

    
    

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
    try:
        # Log the records from the event
        records = event.get('Records', None)
        print("Records:", records)

        if records is None:
            raise ValueError("Event does not contain 'Records' key or it is None")
        
        for element in records:
            print("Processing element:", element)
            try:
                message_attributes = None
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
                        else:
                            print("msg_att_value is empty or None")
                    else:
                        print(f"{msg_att_name} not found in NewImage")
                print("message_attributes", message_attributes)
                if message_attributes is None:
                    message_attributes = {}
                sns_publish(element, topic_arn, table_name, message_attributes)
            except Exception as error:
                print("Error processing element:", error)
        return "Success"
    except Exception as error:
        print("Error in write_sns_to_dynamodb:", error)
        return "Process failed"



def sns_publish(element, topic_arn, table_name, message_attributes):
    try:
        dynamo_item = json.loads(json.dumps(element, default=str))
        dynamo_item['tableName'] = table_name
        print("Dynamo Item to Publish:", dynamo_item)
        print()
        sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(dynamo_item),
            MessageAttributes=message_attributes
        )
        print("SNS Publish successful")
        # else:
        #     print("No DynamoDB item found.")
    except Exception as e:
        print("Error in sns_publish:", e)
        raise Exception("Error publishing to SNS: ") from e

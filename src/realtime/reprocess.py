import json
import os
import datetime
import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from uuid import uuid4
import pytz

dynamodb = boto3.resource('dynamodb')
ddb_client = boto3.client('dynamodb')
# sns_client = boto3.client('sns')

def lambda_handler(event, context):
    print("Received event:", json.dumps(event, indent=2))
    try:
        records = event.get('Records', [])
        process_promises = [process_record(record) for record in records if record.get('eventName') in ['INSERT', 'MODIFY']]

        for promise in process_promises:
            promise

        return {
            'statusCode': 200,
            'body': json.dumps('Processed and inserted DynamoDB stream records successfully')
        }
    except Exception as e:
        print("Handler error:", str(e))
        return {
            'statusCode': 500,
            'body': json.dumps('An error occurred while processing and inserting DynamoDB stream records')
        }

def process_record(record):
    try:
        new_image = record['dynamodb']['NewImage']
        new_image = {k: TypeDeserializer().deserialize(v) for k, v in new_image.items()}

        source_table = new_image.get('Sourcetable', 'default-table-name')
        print("SourceTable:", source_table)

        unique_id = new_image.get('UUid', '')
        print("UniqueID:", unique_id)

        if 'FailedRecord' in new_image:
            process_failed_record(new_image['FailedRecord'], source_table, unique_id)
    except Exception as e:
        print("Process record error:", str(e))

def process_failed_record(failed_record, source_table, unique_id):
    try:
        required_fields = get_required_fields(source_table)
        for field in required_fields:
            if field not in failed_record or not failed_record[field].strip() or failed_record[field].strip().lower() == "null":
                failed_record[field] = str(uuid4())

        print("Updated record:", json.dumps(failed_record, indent=4))

        table = dynamodb.Table(source_table)
        table.put_item(Item=failed_record)

        status = "SUCCESS"
        update_failed_records_table(unique_id, failed_record, source_table, status, "")
        print("Record processed successfully:", failed_record)
    except ClientError as e:
        error_message = str(e)
        sns_params = {
            'TopicArn': os.environ['ERROR_SNS_TOPIC_ARN'],
            'Subject': "An Error occurred while reprocessing failed record",
            'Message': json.dumps({'failedRecord': failed_record, 'error': error_message}),
        }
        # sns_client.publish(**sns_params)

        status = "FAILED"
        update_failed_records_table(unique_id, failed_record, source_table, status, error_message)
        print("Error processing record:", error_message)

def get_required_fields(source_table):
    try:
        response = ddb_client.describe_table(TableName=source_table)
        required_fields = [key['AttributeName'] for key in response['Table']['KeySchema']]
        
        gsi_indexes = response['Table'].get('GlobalSecondaryIndexes', [])
        if gsi_indexes:
            gsi_fields = [key['AttributeName'] for gsi in gsi_indexes for key in gsi['KeySchema']]
            required_fields = list(set(required_fields + gsi_fields))
            print("Required fields from GSIs:", gsi_fields)
        else:
            print("No GlobalSecondaryIndexes found in table description.")
        
        print("Total required fields:", required_fields)
        return required_fields
    except ClientError as e:
        print("Error describing table:", str(e))
        return []

def update_failed_records_table(unique_id, failed_record, source_table, status, error_message):
    try:
        table = dynamodb.Table(os.environ['FAILED_RECORDS'])
        item = {
            'UUid': unique_id,
            'Sourcetable': source_table,
            'FailedRecord': failed_record,
            'Status': status,
            'ErrorMessage': error_message,
            'Timestamp': datetime.datetime.now(pytz.utc)
        }
        table.put_item(Item=item)
        print("Failed record has been reprocessed:", unique_id)
    except ClientError as e:
        print("Error adding failed record to DynamoDB:", str(e))

import os
import datetime
import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from uuid import uuid4

dynamodb = boto3.resource('dynamodb')
ddb_client = boto3.client('dynamodb')

def handler(event, context):
    print("Received event:", event)
    try:
        records = event.get('Records', [])
        for record in records:
            if record.get('eventName') in ['INSERT', 'MODIFY']:
                process_record(record)
        
        return {
            'statusCode': 200,
            'body': 'Processed and inserted DynamoDB stream records successfully'
        }
    except Exception as e:
        print("Handler error:", str(e))
        return {
            'statusCode': 500,
            'body': 'An error occurred while processing and inserting DynamoDB stream records'
        }

def process_record(record):
    try:
        new_image = {k: TypeDeserializer().deserialize(v) for k, v in record['dynamodb']['NewImage'].items()}
        source_table = new_image.get('Sourcetable', 'default-table-name')
        unique_id = new_image.get('UUid', '')
        print(f"Processing record: SourceTable: {source_table}, UniqueID: {unique_id}")

        if 'FailedRecord' in new_image:
            process_failed_record(new_image['FailedRecord'], source_table, unique_id)
    except Exception as e:
        print(f"Process record error: {str(e)}")

def process_failed_record(failed_record, source_table, unique_id):
    try:
        required_fields = get_required_fields(source_table)
        for field in required_fields:
            if not failed_record.get(field) or str(failed_record[field]).strip().lower() == "null":
                failed_record[field] = str(uuid4())

        print("Updated record:", failed_record)

        table = dynamodb.Table(source_table)
        table.put_item(Item=failed_record)

        status = "SUCCESS"
        update_failed_records_table(unique_id, failed_record, source_table, status, "NULL")
        print("Record processed successfully:", failed_record)
    except ClientError as e:
        error_message = str(e)
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
            'Timestamp': datetime.datetime.now().isoformat()
        }
        table.put_item(Item=item)
        print("Failed record has been reprocessed:", unique_id)
    except ClientError as e:
        print("Error adding failed record to DynamoDB:", str(e))
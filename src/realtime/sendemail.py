import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import csv
import io
import os

# Initialize AWS services
dynamodb = boto3.resource('dynamodb')
ses = boto3.client('ses')

EMAIL_TO = "omnidev@bizcloudexperts.com"
EMAIL_FROM = "no-reply@omnilogistics.com"

def handler(event, context):
    start_date = datetime.now().strftime("%Y-%m-%d")
    file_name = f"failed_records_{start_date}.csv"

    try:
        failed_records = fetch_all_failed_records()
        failed_records_count = len(failed_records)

        print(f"Fetched failed records: {failed_records_count}")  # Add this line for debugging

        if failed_records:
            csv_data = generate_csv(failed_records)

            email_params = {
                'Source': EMAIL_FROM,
                'Destination': {
                    'ToAddresses': [EMAIL_TO]
                },
                'Message': {
                    'Subject': {
                        'Data': f"Failed Records Report for Realtime application {start_date}"
                    },
                    'Body': {
                        'Text': {
                            'Data': f"The failed records report for {start_date} has been successfully generated. The file is also attached. There are total {failed_records_count} records."
                        }
                    }
                },
                'Attachments': [
                    {
                        'Filename': file_name,
                        'Content': csv_data,
                        'ContentType': 'text/csv'
                    }
                ]
            }

            ses.send_raw_email(**email_params)
            print("Email sent successfully.")
            return "success"
        else:
            print("No failed records found.")
            return "no failed records"
    except Exception as err:
        print(f"Error querying DynamoDB, generating CSV, or sending email: {err}")
        raise

def fetch_all_failed_records():
    table = dynamodb.Table(os.environ['FAILED_RECORDS'])
    all_records = []
    last_evaluated_key = None

    try:
        while True:
            params = {
                'IndexName': 'Status-index',  # Replace with the actual name of your GSI
                'KeyConditionExpression': '#Status = :FAILED',
                'ExpressionAttributeNames': {
                    '#Status': 'Status'
                },
                'ExpressionAttributeValues': {
                    ':FAILED': 'FAILED'
                },
                'Limit': 10000  # Adjust the batch size as per your needs
            }

            if last_evaluated_key:
                params['ExclusiveStartKey'] = last_evaluated_key

            response = table.query(**params)
            all_records.extend(response.get('Items', []))
            
            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break

    except ClientError as e:
        print(f"Query failed: {e}")
        raise

    return all_records

def generate_csv(records):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader()
    for record in records:
        writer.writerow(record)
    return output.getvalue()
import boto3
import csv
import os
from io import StringIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Initialize clients
dynamodb = boto3.client('dynamodb')
ses = boto3.client('ses')

# Environment variables
TABLE_NAME = os.environ['FAILED_RECORDS']
SENDER_EMAIL = os.environ['TO_EMAIL']
RECIPIENT_EMAIL = os.environ['FROM_EMAIL']

def handler(event, context):
    # Scan DynamoDB table for records with status 'SUCCESS'
    response = dynamodb.scan(
        TableName=TABLE_NAME,
        FilterExpression='#status = :status',
        ExpressionAttributeNames={'#status': 'Status'},
        ExpressionAttributeValues={':status': {'S': 'FAILED'}}
    )

    records = response['Items']
    print(records)
    
    if not records:
        return {"message": "No records found with status 'FAILED'"}

    # Create CSV
    csv_content = generate_csv(records)

    # Send email with CSV attachment
    send_email(csv_content)

    return {"message": "Email sent successfully"}

def generate_csv(records):
    # Create a CSV string
    csv_file = StringIO()
    csv_writer = csv.writer(csv_file)

    # Write headers
    headers = records[0].keys()
    csv_writer.writerow(headers)

    # Write data
    for record in records:
        row = []
        for header in headers:
            value = record[header]
            if 'S' in value:
                row.append(value['S'])
            elif 'N' in value:
                row.append(value['N'])
            elif 'B' in value:
                row.append(value['B'])
            else:
                row.append(str(value))  # Handle other data types or nested structures
        csv_writer.writerow(row)

    return csv_file.getvalue()

def send_email(csv_content):
    # Create raw email
    msg = MIMEMultipart()
    msg['Subject'] = "Failed Records Report"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL

    # Email body
    body = MIMEText("Please find the attached CSV file containing records with status 'SUCCESS'.")
    msg.attach(body)

    # CSV attachment
    attachment = MIMEApplication(csv_content)
    attachment.add_header('Content-Disposition', 'attachment', filename='failed_records.csv')
    msg.attach(attachment)

    # Send email
    response = ses.send_raw_email(
        Source=SENDER_EMAIL,
        Destinations=[RECIPIENT_EMAIL],
        RawMessage={'Data': msg.as_string()}
    )
    
    return response








## USED TO CHANGE STATUS OF RECORDS
# import os
# import boto3
# from boto3.dynamodb.conditions import Key

# # Assume environment variable is set for the table name
# table_name = os.getenv('FAILED_RECORDS')

# # Initialize a session using Amazon DynamoDB
# dynamodb = boto3.resource('dynamodb')

# # Select the DynamoDB table
# table = dynamodb.Table(table_name)

# # Define a lambda function for filtering items with Status 'INSERTED'
# get_inserted_items = lambda: table.query(
#     IndexName='Status-index',  # Use the appropriate index name if using a GSI
#     KeyConditionExpression=Key('Status').eq('FAILED')
# )['Items']

# # Function to update the status of the items to 'FAILED'
# def update_inserted_to_failed():
#     inserted_items = get_inserted_items()
#     with table.batch_writer() as batch:
#         for item in inserted_items:
#             item['Status'] = 'INSERTED'
#             batch.put_item(Item=item)

# # Lambda handler function
# def handler(event, context):
#     update_inserted_to_failed()
#     return {
#         'statusCode': 200,
#         'body': 'Updated items with status INSERTED to FAILED'
#     }


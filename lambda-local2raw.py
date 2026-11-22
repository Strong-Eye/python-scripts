import base64
import json
import os
import boto3

s3 = boto3.client("s3")
TOKENS = json.loads(os.environ["TOKENS"])

def lambda_handler(event, context):
    if event["headers"].get("x-api-key") not in TOKENS:
        return {"statusCode": 401, "body": "não autorizado"}

    nome = os.path.basename(event["queryStringParameters"]["nome"])
    corpo = event["body"]
    corpo = base64.b64decode(corpo) if event["isBase64Encoded"] else corpo.encode()

    s3.put_object(Bucket=os.environ["BUCKET_NAME"], Key=f"raw/{nome}", Body=corpo)
    return {"statusCode": 200, "body": f"raw/{nome}"}
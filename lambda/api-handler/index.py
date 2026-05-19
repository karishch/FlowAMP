import json
import os
import boto3

bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')
AGENT_ID = os.environ['BEDROCK_AGENT_ID']
AGENT_ALIAS_ID = os.environ.get('BEDROCK_AGENT_ALIAS_ID', 'TSTALIASID')


def handler(event, context):
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'POST,OPTIONS',
    }

    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    body = json.loads(event.get('body', '{}'))
    prompt = body.get('prompt', '')
    session_id = body.get('sessionId', context.aws_request_id)

    if not prompt:
        return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'No prompt'})}

    response = bedrock_agent_runtime.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=session_id,
        inputText=prompt,
    )

    result = ''
    for event_chunk in response.get('completion', []):
        if 'chunk' in event_chunk:
            result += event_chunk['chunk']['bytes'].decode('utf-8')

    return {
        'statusCode': 200,
        'headers': headers,
        'body': json.dumps({'response': result, 'sessionId': session_id}),
    }

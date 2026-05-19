import os
import json
import boto3
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

ddb = boto3.resource('dynamodb')
table = ddb.Table(os.environ.get('AGENT_TABLE_NAME', 'AgentTable'))


@tool
def list_agents() -> str:
    """List all registered AI agents across energy systems."""
    items = table.scan().get('Items', [])
    return json.dumps(items, default=str)


@tool
def get_agent(agent_id: str) -> str:
    """Get details of a specific AI agent by its ID."""
    item = table.get_item(Key={'agentId': agent_id}).get('Item', {})
    return json.dumps(item, default=str)


@tool
def get_agent_metrics(agent_id: str) -> str:
    """Get performance metrics (requests, errors, response time) for an agent."""
    item = table.get_item(Key={'agentId': agent_id}).get('Item', {})
    return json.dumps({k: item.get(k) for k in
        ['agentId', 'name', 'requests', 'errors', 'avgResponseMs', 'status']}, default=str)


model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

agent = Agent(
    model=model,
    tools=[list_agents, get_agent, get_agent_metrics],
    system_prompt="""You are an AI agent management assistant for an energy utility company.
You help operators monitor and manage AI agents deployed across grid operations,
asset management, energy trading, safety compliance, and customer operations.
Always use the available tools to fetch real data before responding.""",
)


def handler(event, context):
    """HTTP handler for AgentCore Runtime."""
    body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event.get('body', {})
    prompt = body.get('prompt', body.get('message', ''))
    if not prompt:
        return {'statusCode': 400, 'body': json.dumps({'error': 'No prompt provided'})}

    result = agent(prompt)
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'response': str(result)})
    }


if __name__ == '__main__':
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            result = handler({'body': body}, None)
            self.send_response(result['statusCode'])
            for k, v in result.get('headers', {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(result['body'].encode())

    port = int(os.environ.get('PORT', '8080'))
    print(f"Starting agent on port {port}")
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()

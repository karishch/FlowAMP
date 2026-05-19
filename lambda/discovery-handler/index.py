"""
Discovery Agent — polls external platforms and upserts normalized agent records.

Supports: Microsoft Copilot Studio, Okta Secure AI, MuleSoft Agent Fabric.
Each connector returns a list of normalized dicts that map to the AgentRecord schema.
Runs on a schedule (EventBridge) or on-demand via API Gateway.
"""
import json, os, time, logging
from datetime import datetime, timezone
from decimal import Decimal
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ddb = boto3.resource('dynamodb')
table = ddb.Table(os.environ['AGENT_TABLE_NAME'])
secrets = boto3.client('secretsmanager')

NOW = datetime.now(timezone.utc).isoformat()

# ── Helpers ──

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def upsert_agent(agent: dict):
    """Write a normalized agent record. Preserves RAI scores if they exist."""
    existing = table.get_item(Key={'agentId': agent['agentId']}).get('Item', {})
    # Keep RAI scores from previous runs — discovery doesn't overwrite them
    for k in ('score', 'fairness', 'transparency', 'accountability', 'ethics'):
        if k not in agent or agent[k] == 0:
            agent[k] = existing.get(k, 0)
    agent['lastSyncedAt'] = NOW
    agent.setdefault('discoveredAt', existing.get('discoveredAt', NOW))
    # Convert floats to Decimal for DynamoDB
    agent = json.loads(json.dumps(agent, default=decimal_default), parse_float=Decimal)
    table.put_item(Item=agent)


# ═══════════════════════════════════════════════════════════════
# Microsoft Copilot Studio connector
# ═══════════════════════════════════════════════════════════════

MSFT_SIMULATED_AGENTS = [
    {"platformAgentId": "copilot-it-helpdesk", "name": "IT Helpdesk Copilot", "category": "IT Operations", "status": "active", "requests": 14200, "errors": 45, "avgResponseMs": 320, "utilization": 87, "monthlyCost": 1200, "costPerInvocation": 0.0015, "owner": "IT Department"},
    {"platformAgentId": "copilot-hr-onboarding", "name": "HR Onboarding Assistant", "category": "Human Resources", "status": "active", "requests": 3400, "errors": 8, "avgResponseMs": 450, "utilization": 62, "monthlyCost": 800, "costPerInvocation": 0.0020, "owner": "HR Team"},
    {"platformAgentId": "copilot-finance-reporting", "name": "Finance Reporting Copilot", "category": "Finance", "status": "active", "requests": 5600, "errors": 12, "avgResponseMs": 280, "utilization": 74, "monthlyCost": 950, "costPerInvocation": 0.0012, "owner": "Finance"},
    {"platformAgentId": "copilot-safety-docs", "name": "Safety Documentation Copilot", "category": "Safety & Compliance", "status": "active", "requests": 2100, "errors": 3, "avgResponseMs": 380, "utilization": 55, "monthlyCost": 600, "costPerInvocation": 0.0018, "owner": "EHS"},
    {"platformAgentId": "copilot-procurement", "name": "Procurement Assistant", "category": "Supply Chain", "status": "warning", "requests": 1800, "errors": 34, "avgResponseMs": 520, "utilization": 48, "monthlyCost": 700, "costPerInvocation": 0.0022, "owner": "Procurement"},
]

def discover_microsoft(config: dict) -> list:
    """
    In production: call Microsoft Graph / Copilot Studio Management API.
    For demo: return simulated agents.
    """
    # TODO: real implementation would use:
    # endpoint = config.get('endpoint', 'https://graph.microsoft.com/v1.0')
    # creds = json.loads(secrets.get_secret_value(SecretId=config['credentialArn'])['SecretString'])
    agents = []
    for src in MSFT_SIMULATED_AGENTS:
        agents.append({
            'agentId': f"msft:{src['platformAgentId']}",
            'name': src['name'],
            'platform': 'microsoft',
            'platformAgentId': src['platformAgentId'],
            'category': src['category'],
            'system': 'Copilot Studio',
            'status': src['status'],
            'requests': src['requests'],
            'errors': src['errors'],
            'avgResponseMs': src['avgResponseMs'],
            'utilization': src['utilization'],
            'monthlyCost': src['monthlyCost'],
            'costPerInvocation': src['costPerInvocation'],
            'score': 0, 'fairness': 0, 'transparency': 0, 'accountability': 0, 'ethics': 0,
            'owner': src.get('owner', ''),
            'platformMetadata': {'source': 'copilot-studio', 'tenant': 'energy-corp'},
        })
    return agents


# ═══════════════════════════════════════════════════════════════
# Okta Secure AI connector
# ═══════════════════════════════════════════════════════════════

OKTA_SIMULATED_AGENTS = [
    {"platformAgentId": "okta-identity-governance", "name": "Identity Governance Agent", "category": "Security", "status": "active", "requests": 9800, "errors": 5, "avgResponseMs": 95, "utilization": 92, "monthlyCost": 450, "costPerInvocation": 0.0003, "owner": "IAM Team"},
    {"platformAgentId": "okta-access-certifier", "name": "Access Certification Agent", "category": "Security", "status": "active", "requests": 4500, "errors": 2, "avgResponseMs": 180, "utilization": 78, "monthlyCost": 350, "costPerInvocation": 0.0005, "owner": "IAM Team"},
    {"platformAgentId": "okta-threat-detector", "name": "Agent Threat Detector", "category": "Security", "status": "active", "requests": 22000, "errors": 18, "avgResponseMs": 42, "utilization": 96, "monthlyCost": 680, "costPerInvocation": 0.0001, "owner": "SOC"},
    {"platformAgentId": "okta-policy-enforcer", "name": "AI Policy Enforcer", "category": "Safety & Compliance", "status": "active", "requests": 15600, "errors": 7, "avgResponseMs": 65, "utilization": 94, "monthlyCost": 520, "costPerInvocation": 0.0002, "owner": "Security Ops"},
]

def discover_okta(config: dict) -> list:
    """
    In production: call Okta Admin API + Secure AI endpoints.
    For demo: return simulated agents.
    """
    agents = []
    for src in OKTA_SIMULATED_AGENTS:
        agents.append({
            'agentId': f"okta:{src['platformAgentId']}",
            'name': src['name'],
            'platform': 'okta',
            'platformAgentId': src['platformAgentId'],
            'category': src['category'],
            'system': 'Okta Secure AI',
            'status': src['status'],
            'requests': src['requests'],
            'errors': src['errors'],
            'avgResponseMs': src['avgResponseMs'],
            'utilization': src['utilization'],
            'monthlyCost': src['monthlyCost'],
            'costPerInvocation': src['costPerInvocation'],
            'score': 0, 'fairness': 0, 'transparency': 0, 'accountability': 0, 'ethics': 0,
            'owner': src.get('owner', ''),
            'platformMetadata': {'source': 'okta-secure-ai', 'org': 'energy-corp.okta.com'},
        })
    return agents


# ═══════════════════════════════════════════════════════════════
# MuleSoft Agent Fabric connector
# ═══════════════════════════════════════════════════════════════

MULESOFT_SIMULATED_AGENTS = [
    {"platformAgentId": "mule-sap-invoice", "name": "SAP Invoice Processor", "category": "Finance", "status": "active", "requests": 7800, "errors": 22, "avgResponseMs": 410, "utilization": 83, "monthlyCost": 1100, "costPerInvocation": 0.0010, "owner": "Finance Ops"},
    {"platformAgentId": "mule-salesforce-lead", "name": "Salesforce Lead Qualifier", "category": "Customer Operations", "status": "active", "requests": 6200, "errors": 15, "avgResponseMs": 290, "utilization": 79, "monthlyCost": 890, "costPerInvocation": 0.0008, "owner": "Sales"},
    {"platformAgentId": "mule-servicenow-ticket", "name": "ServiceNow Ticket Router", "category": "IT Operations", "status": "active", "requests": 11400, "errors": 28, "avgResponseMs": 185, "utilization": 88, "monthlyCost": 760, "costPerInvocation": 0.0004, "owner": "IT Service Mgmt"},
    {"platformAgentId": "mule-workday-hr", "name": "Workday HR Data Agent", "category": "Human Resources", "status": "active", "requests": 2900, "errors": 6, "avgResponseMs": 350, "utilization": 61, "monthlyCost": 540, "costPerInvocation": 0.0011, "owner": "HR Ops"},
    {"platformAgentId": "mule-scada-bridge", "name": "SCADA Data Bridge Agent", "category": "Grid Operations", "status": "active", "requests": 18500, "errors": 9, "avgResponseMs": 55, "utilization": 95, "monthlyCost": 430, "costPerInvocation": 0.0001, "owner": "OT Integration"},
    {"platformAgentId": "mule-maximo-sync", "name": "Maximo Work Order Sync", "category": "Asset Management", "status": "warning", "requests": 3400, "errors": 41, "avgResponseMs": 480, "utilization": 67, "monthlyCost": 620, "costPerInvocation": 0.0009, "owner": "Asset Mgmt"},
]

def discover_mulesoft(config: dict) -> list:
    """
    In production: call MuleSoft Anypoint Platform API.
    For demo: return simulated agents.
    """
    agents = []
    for src in MULESOFT_SIMULATED_AGENTS:
        agents.append({
            'agentId': f"mule:{src['platformAgentId']}",
            'name': src['name'],
            'platform': 'mulesoft',
            'platformAgentId': src['platformAgentId'],
            'category': src['category'],
            'system': 'MuleSoft Agent Fabric',
            'status': src['status'],
            'requests': src['requests'],
            'errors': src['errors'],
            'avgResponseMs': src['avgResponseMs'],
            'utilization': src['utilization'],
            'monthlyCost': src['monthlyCost'],
            'costPerInvocation': src['costPerInvocation'],
            'score': 0, 'fairness': 0, 'transparency': 0, 'accountability': 0, 'ethics': 0,
            'owner': src.get('owner', ''),
            'platformMetadata': {'source': 'anypoint-agent-fabric', 'org': 'energy-corp'},
        })
    return agents


# ═══════════════════════════════════════════════════════════════
# Dispatcher
# ═══════════════════════════════════════════════════════════════

CONNECTORS = {
    'microsoft': discover_microsoft,
    'okta': discover_okta,
    'mulesoft': discover_mulesoft,
}

def run_discovery(platforms: list[str] | None = None) -> list[dict]:
    """Run discovery for specified platforms (or all if None)."""
    targets = platforms or list(CONNECTORS.keys())
    results = []
    for p in targets:
        if p not in CONNECTORS:
            results.append({'platform': p, 'error': f'Unknown platform: {p}'})
            continue
        try:
            config = {}  # In production: load from SSM Parameter Store
            agents = CONNECTORS[p](config)
            updated = 0
            for agent in agents:
                upsert_agent(agent)
                updated += 1
            results.append({
                'platform': p,
                'agentsDiscovered': len(agents),
                'agentsUpdated': updated,
                'agentsRemoved': 0,
                'syncedAt': NOW,
            })
            logger.info(f"Discovered {len(agents)} agents from {p}")
        except Exception as e:
            logger.error(f"Discovery failed for {p}: {e}")
            results.append({'platform': p, 'error': str(e), 'syncedAt': NOW})
    return results


def handler(event, context):
    """
    Invoked by:
      - EventBridge schedule (no body → sync all platforms)
      - API Gateway POST /discovery/sync (body.platforms → selective sync)
      - API Gateway GET /discovery/status (return last sync info)
    """
    # EventBridge scheduled invocation
    if 'source' in event and event['source'] == 'aws.events':
        results = run_discovery()
        return {'statusCode': 200, 'body': json.dumps(results, default=decimal_default)}

    # API Gateway
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    }

    if http_method == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    if http_method == 'POST' and '/sync' in path:
        body = json.loads(event.get('body', '{}') or '{}')
        platforms = body.get('platforms')  # None = all
        results = run_discovery(platforms)
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps(results, default=decimal_default)}

    if http_method == 'GET' and '/status' in path:
        # Return counts per platform from DynamoDB
        items = table.scan().get('Items', [])
        agents = [i for i in items if not i['agentId'].startswith(('compliance:', 'aop:', 'access:'))]
        summary = {}
        for a in agents:
            p = a.get('platform', 'native')
            if p not in summary:
                summary[p] = {'count': 0, 'active': 0, 'lastSynced': None}
            summary[p]['count'] += 1
            if a.get('status') == 'active':
                summary[p]['active'] += 1
            ls = a.get('lastSyncedAt')
            if ls and (not summary[p]['lastSynced'] or ls > summary[p]['lastSynced']):
                summary[p]['lastSynced'] = ls
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps(summary, default=decimal_default)}

    if http_method == 'GET' and '/platforms' in path:
        return {
            'statusCode': 200, 'headers': headers,
            'body': json.dumps([
                {'platform': 'native', 'name': 'AWS Bedrock / Strands', 'status': 'connected'},
                {'platform': 'microsoft', 'name': 'Microsoft Copilot Studio', 'status': 'connected'},
                {'platform': 'okta', 'name': 'Okta Secure AI', 'status': 'connected'},
                {'platform': 'mulesoft', 'name': 'MuleSoft Agent Fabric', 'status': 'connected'},
            ])
        }

    return {'statusCode': 404, 'headers': headers, 'body': json.dumps({'error': 'Not found'})}

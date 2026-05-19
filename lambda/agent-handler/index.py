import json
import os
import boto3
from decimal import Decimal

ddb = boto3.resource('dynamodb')
table = ddb.Table(os.environ['AGENT_TABLE_NAME'])

PREFIXES = ('compliance:', 'aop:', 'access:')

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal): return float(o)
        return super().default(o)

def get_all_agents(platform=None):
    items = [i for i in table.scan().get('Items', []) if not i['agentId'].startswith(PREFIXES)]
    if platform:
        items = [i for i in items if i.get('platform', 'native') == platform]
    return items

def scan_by_prefix(prefix):
    return [i for i in table.scan().get('Items', []) if i['agentId'].startswith(prefix)]

def handler(event, context):
    api_path = event.get('apiPath', '')
    action = event.get('actionGroup', '')
    params = {p['name']: p['value'] for p in event.get('parameters', [])}

    if api_path == '/agents':
        items = get_all_agents(params.get('platform'))
        body = json.dumps(items, cls=DecimalEncoder)

    elif api_path == '/agents/cross-platform-summary':
        agents = get_all_agents()
        total_cost = sum(float(a.get('monthlyCost', 0)) for a in agents)
        total_req = sum(int(a.get('requests', 0)) for a in agents)
        total_err = sum(int(a.get('errors', 0)) for a in agents)
        scores = [float(a.get('score', 0)) for a in agents if float(a.get('score', 0)) > 0]
        breakdown = {}
        for a in agents:
            p = a.get('platform', 'native')
            if p not in breakdown:
                breakdown[p] = {'count': 0, 'active': 0, 'cost': 0}
            breakdown[p]['count'] += 1
            if a.get('status') == 'active':
                breakdown[p]['active'] += 1
            breakdown[p]['cost'] += float(a.get('monthlyCost', 0))
        body = json.dumps({
            'totalAgents': len(agents),
            'totalMonthlyCost': round(total_cost, 2),
            'avgRaiScore': round(sum(scores) / len(scores), 1) if scores else 0,
            'totalRequests': total_req,
            'totalErrors': total_err,
            'platformBreakdown': json.dumps(breakdown),
        })

    elif api_path == '/platforms':
        agents = get_all_agents()
        platforms = {}
        for a in agents:
            p = a.get('platform', 'native')
            if p not in platforms:
                platforms[p] = {'platform': p, 'agentCount': 0, 'activeCount': 0, 'totalMonthlyCost': 0, 'raiScores': [], 'lastSyncedAt': None}
            platforms[p]['agentCount'] += 1
            if a.get('status') == 'active':
                platforms[p]['activeCount'] += 1
            platforms[p]['totalMonthlyCost'] += float(a.get('monthlyCost', 0))
            s = float(a.get('score', 0))
            if s > 0:
                platforms[p]['raiScores'].append(s)
            ls = a.get('lastSyncedAt')
            if ls and (not platforms[p]['lastSyncedAt'] or ls > platforms[p]['lastSyncedAt']):
                platforms[p]['lastSyncedAt'] = ls
        result = []
        for v in platforms.values():
            scores = v.pop('raiScores')
            v['avgRaiScore'] = round(sum(scores) / len(scores), 1) if scores else 0
            v['totalMonthlyCost'] = round(v['totalMonthlyCost'], 2)
            result.append(v)
        body = json.dumps(result)

    elif api_path == '/agents/{agentId}':
        body = json.dumps(table.get_item(Key={'agentId': params['agentId']}).get('Item', {}), cls=DecimalEncoder)

    elif api_path == '/agents/{agentId}/metrics':
        item = table.get_item(Key={'agentId': params['agentId']}).get('Item', {})
        body = json.dumps({k: item.get(k) for k in ['agentId', 'requests', 'errors', 'avgResponseMs', 'status', 'monthlyCost', 'costPerInvocation', 'utilization', 'platform']}, cls=DecimalEncoder)

    elif api_path == '/compliance':
        body = json.dumps(scan_by_prefix('compliance:'), cls=DecimalEncoder)
    elif api_path == '/aops':
        body = json.dumps(scan_by_prefix('aop:'), cls=DecimalEncoder)
    elif api_path == '/access':
        body = json.dumps(scan_by_prefix('access:'), cls=DecimalEncoder)
    else:
        body = json.dumps({'message': 'Unknown action'})

    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': action,
            'apiPath': api_path,
            'httpMethod': event.get('httpMethod', 'GET'),
            'httpStatusCode': 200,
            'responseBody': {'application/json': {'body': body}}
        }
    }

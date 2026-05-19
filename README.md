# FlowAMP

FlowAMP is an AI agent governance and compliance starter kit for energy utilities. It gives operators a single control plane for discovering, monitoring, scoring, and governing AI agents that interact with critical energy workflows such as grid operations, asset management, trading, safety, compliance, and customer operations.

The project is implemented as an AWS CDK TypeScript stack with Lambda, DynamoDB, API Gateway, Amazon Bedrock, Bedrock AgentCore, S3, and CloudFront.

## Live Demo

Open the hosted FlowAMP demo: [https://d1ox9mx07nnxxx.cloudfront.net](https://d1ox9mx07nnxxx.cloudfront.net)

## Why This Exists

AI agents are moving from pilots into operational environments where they may access ADMS, SCADA, Maximo, AMI, customer systems, market data, and compliance workflows. At that point, teams need more than isolated agent demos. They need enforceable boundaries, cost visibility, audit trails, access control, and continuous compliance evidence.

FlowAMP is designed to help answer:

- What agents exist, who owns them, and what systems do they touch?
- Which agents are active, warning, failing, or decommissioned?
- How do agents score against responsible AI dimensions?
- Which operating policies and escalation paths apply to each workflow?
- Who can invoke which agents?
- What does each agent cost, and which business unit should own the spend?
- What evidence can be shown to regulators, auditors, and security teams?

## Core Capabilities

- **Agent registry and lifecycle**: Central catalog of agents, owners, categories, systems, status, and lifecycle state.
- **Compliance center**: Framework-oriented scoring for energy, cybersecurity, and AI governance obligations such as NERC CIP, FERC standards, EPA emissions, SOC 2, DOE cybersecurity guidance, and NIST AI RMF.
- **Responsible AI scoring**: Per-agent scoring for fairness, transparency, accountability, and ethics using AWS operational signals.
- **Agent operating policies**: Policy model for trigger conditions, agent assignments, guardrail constraints, boundary limits, escalation rules, and audit requirements.
- **Access control and identity**: Role-based permission model across agent categories, with a path toward IAM, IdP, and AgentCore policy integration.
- **FinOps intelligence**: Agent-level spend visibility, cost anomaly detection, chargeback by business unit, and optimization recommendations.
- **Executive dashboard and demo UI**: CloudFront-hosted interface for registry, governance, compliance, AOP, access, FinOps, and chat workflows.

## AWS Architecture

The CDK stack provisions:

- DynamoDB table for normalized agent records
- Lambda functions for agent action handling, API chat, discovery sync, seed data, and responsible AI scoring
- EventBridge schedules for recurring discovery and scoring jobs
- Amazon Bedrock Agent with an action group backed by Lambda
- Bedrock AgentCore Runtime endpoint for the Python Strands agent
- API Gateway REST API with `/chat` and `/discovery` routes
- S3 bucket and CloudFront distribution for the demo web application

The intended AWS signal sources include Security Hub, AWS Config, CloudTrail, IAM Access Analyzer, GuardDuty, CloudWatch, Inspector, Bedrock Guardrails, Cost Explorer, and AgentCore Observability.

## Repository Layout

```text
.
|-- agents/energy-agent/          # AgentCore runtime artifact
|-- bin/                          # CDK app entrypoint
|-- demo/                         # Static FlowAMP demo UI
|-- lambda/
|   |-- agent-handler/            # Bedrock Agent action group handler
|   |-- api-handler/              # API Gateway chat handler
|   |-- discovery-handler/        # Multi-platform agent discovery sync
|   |-- rai-scorer/               # Responsible AI scoring job
|   `-- seed-data/                # Initial demo data loader
|-- lib/                          # CDK stack and shared schema
|-- test/                         # Jest CDK tests
|-- cdk.json
`-- package.json
```

## Prerequisites

- Node.js 20 or newer
- AWS CLI configured for the target account
- AWS CDK v2
- Docker, if your environment requires local asset bundling
- Access to Amazon Bedrock and the referenced foundation model or inference profile

The stack defaults to `us-east-1` when `CDK_DEFAULT_REGION` is not set.

## Getting Started

Install dependencies:

```bash
npm install
```

Build the TypeScript project:

```bash
npm run build
```

Run tests:

```bash
npm test
```

Synthesize CloudFormation:

```bash
npx cdk synth
```

Deploy:

```bash
npx cdk deploy
```

After deployment, CDK outputs include:

- `DemoUrl`: CloudFront URL for the FlowAMP demo UI
- `ApiUrl`: API Gateway base URL
- `AgentTableName`: DynamoDB table for agent records
- `BedrockAgentId`: Bedrock Agent identifier
- `AgentCoreRuntimeArn`: AgentCore runtime ARN
- `AgentCoreEndpointArn`: AgentCore endpoint ARN

## Operating Model

A typical rollout can follow three phases:

1. **Foundation**: Deploy the starter kit, register agents, enable Security Hub and Config, and apply resource tags such as `AgentId`, `BusinessUnit`, and `CostCenter`.
2. **Governance**: Define operating policies for high-risk workflows, add Cedar policy rules, enable Bedrock Guardrails, and activate responsible AI scoring.
3. **Operations**: Turn on compliance scoring, FinOps chargeback, AgentCore Observability, and IdP integration.

## Notes

- This is a starter kit and demo implementation, not a finished production control plane.
- The stack uses `RemovalPolicy.DESTROY` for demo resources, including the DynamoDB table and static site bucket.
- Review IAM permissions, model access, data retention, audit requirements, and network boundaries before using this in a production environment.

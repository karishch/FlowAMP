import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as bedrock from '@aws-cdk/aws-bedrock-alpha';
import * as agentcore from '@aws-cdk/aws-bedrock-agentcore-alpha';
import { Construct } from 'constructs';
import * as path from 'path';
import * as fs from 'fs';

export class EnergyPlatformStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ─── DynamoDB ───
    const agentTable = new dynamodb.Table(this, 'AgentTable', {
      partitionKey: { name: 'agentId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ─── Lambda: Bedrock Agent action group handler ───
    const agentHandlerFn = new lambda.Function(this, 'AgentHandlerFn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', 'agent-handler')),
      environment: { AGENT_TABLE_NAME: agentTable.tableName },
      timeout: cdk.Duration.seconds(30),
    });
    agentTable.grantReadData(agentHandlerFn);

    // ─── Seed DynamoDB ───
    const seedFn = new lambda.Function(this, 'SeedDataFn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', 'seed-data')),
      environment: { AGENT_TABLE_NAME: agentTable.tableName },
      timeout: cdk.Duration.seconds(60),
    });
    agentTable.grantWriteData(seedFn);

    const seedProvider = new cr.Provider(this, 'SeedProvider', { onEventHandler: seedFn });
    new cdk.CustomResource(this, 'SeedData', { serviceToken: seedProvider.serviceToken });

    // ─── Discovery Agent (multi-platform sync) ───
    const discoveryFn = new lambda.Function(this, 'DiscoveryHandlerFn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', 'discovery-handler')),
      environment: { AGENT_TABLE_NAME: agentTable.tableName },
      timeout: cdk.Duration.seconds(120),
    });
    agentTable.grantReadWriteData(discoveryFn);

    new events.Rule(this, 'DiscoverySyncSchedule', {
      schedule: events.Schedule.rate(cdk.Duration.hours(6)),
      description: 'Sync agents from Microsoft, Okta, MuleSoft every 6 hours',
    }).addTarget(new targets.LambdaFunction(discoveryFn));

    // ─── RAI Scorer (daily) ───
    const raiScorerFn = new lambda.Function(this, 'RaiScorerFn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', 'rai-scorer')),
      environment: { AGENT_TABLE_NAME: agentTable.tableName },
      timeout: cdk.Duration.seconds(120),
    });
    agentTable.grantReadWriteData(raiScorerFn);
    raiScorerFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['cloudwatch:GetMetricStatistics', 'cloudwatch:ListMetrics'],
      resources: ['*'],
    }));
    raiScorerFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['cloudtrail:LookupEvents'],
      resources: ['*'],
    }));
    new events.Rule(this, 'RaiScorerSchedule', {
      schedule: events.Schedule.rate(cdk.Duration.days(1)),
    }).addTarget(new targets.LambdaFunction(raiScorerFn));

    // ─── Bedrock Agent ───
    const inferenceProfileId = 'us.anthropic.claude-sonnet-4-20250514-v1:0';
    const inferenceProfileArn = `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/${inferenceProfileId}`;

    const agent = new bedrock.Agent(this, 'EnergyAgent', {
      foundationModel: new bedrock.BedrockFoundationModel(inferenceProfileId, { supportsAgents: true }),
      instruction: `You are an AI agent management assistant for an energy utility company.
You help operators monitor and manage AI agents deployed across grid operations,
asset management, energy trading, safety compliance, and customer operations.
Use the available tools to fetch real data before responding.`,
    });

    // Override the foundation model ARN to use inference-profile instead of foundation-model
    const cfnAgent = agent.node.defaultChild as cdk.CfnResource;
    cfnAgent.addPropertyOverride('FoundationModel', inferenceProfileArn);

    // Grant the agent role permission to use the inference profile
    agent.role.addToPrincipalPolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel*', 'bedrock:GetInferenceProfile'],
      resources: [
        inferenceProfileArn,
        `arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-20250514-v1:0`,
      ],
    }));

    agent.addActionGroup(new bedrock.AgentActionGroup({
      name: 'AgentManagement',
      apiSchema: bedrock.ApiSchema.fromInline(
        fs.readFileSync(path.join(__dirname, '..', 'lambda', 'agent-handler', 'openapi.json'), 'utf-8')
      ),
      executor: bedrock.ActionGroupExecutor.fromLambda(agentHandlerFn),
    }));

    // ─── AgentCore Runtime (Strands agent) ───
    const agentRuntime = new agentcore.Runtime(this, 'EnergyAgentRuntime', {
      runtimeName: 'energyAgentRuntime',
      agentRuntimeArtifact: agentcore.AgentRuntimeArtifact.fromCodeAsset({
        path: path.join(__dirname, '..', 'agents', 'energy-agent'),
        runtime: agentcore.AgentCoreRuntime.PYTHON_3_12,
        entrypoint: ['main.py'],
      }),
      environmentVariables: {
        AGENT_TABLE_NAME: agentTable.tableName,
        PORT: '8080',
      },
      description: 'Energy AI Agent Management Runtime powered by Strands',
    });
    agentTable.grantReadData(agentRuntime);
    agentRuntime.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel*', 'bedrock:GetInferenceProfile'],
      resources: [
        inferenceProfileArn,
        `arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-20250514-v1:0`,
      ],
    }));

    const agentEndpoint = agentRuntime.addEndpoint('energyAgentEndpoint', {
      description: 'Energy Agent Management API endpoint',
    });

    // ─── API Gateway: Frontend → Bedrock Agent ───
    const apiFn = new lambda.Function(this, 'ApiHandlerFn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', 'api-handler')),
      environment: {
        BEDROCK_AGENT_ID: agent.agentId,
        BEDROCK_AGENT_ALIAS_ID: 'TSTALIASID',
      },
      timeout: cdk.Duration.seconds(120),
    });

    apiFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeAgent'],
      resources: [`arn:aws:bedrock:${this.region}:${this.account}:agent-alias/${agent.agentId}/*`],
    }));

    const api = new apigateway.RestApi(this, 'EnergyAgentApi', {
      restApiName: 'Energy Agent API',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: ['GET', 'POST', 'OPTIONS'],
        allowHeaders: ['Content-Type'],
      },
    });

    api.root.addResource('chat').addMethod('POST',
      new apigateway.LambdaIntegration(apiFn)
    );

    // Discovery API routes
    const discoveryResource = api.root.addResource('discovery');
    const discoveryIntegration = new apigateway.LambdaIntegration(discoveryFn);
    discoveryResource.addResource('sync').addMethod('POST', discoveryIntegration);
    discoveryResource.addResource('status').addMethod('GET', discoveryIntegration);
    discoveryResource.addResource('platforms').addMethod('GET', discoveryIntegration);

    // ─── S3 + CloudFront ───
    const siteBucket = new s3.Bucket(this, 'DemoSiteBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    const distribution = new cloudfront.Distribution(this, 'DemoDistribution', {
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(siteBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
      defaultRootObject: 'energy-agent-management.html',
    });

    new s3deploy.BucketDeployment(this, 'DeploySite', {
      sources: [
        s3deploy.Source.asset(path.join(__dirname, '..', 'demo'), {
          exclude: ['*.pptx', '*.docx', '*.py', '*.md', '.DS_Store', 'generated-diagrams/**'],
        }),
        s3deploy.Source.data('config.js', `window.CHAT_API_URL="${api.url}chat";`),
      ],
      destinationBucket: siteBucket,
      distribution,
      distributionPaths: ['/*'],
    });

    // ─── Outputs ───
    new cdk.CfnOutput(this, 'DemoUrl', {
      value: `https://${distribution.distributionDomainName}`,
      description: 'Energy Agent Management Platform URL',
    });
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: api.url,
      description: 'API Gateway URL (POST /chat)',
    });
    new cdk.CfnOutput(this, 'AgentTableName', { value: agentTable.tableName });
    new cdk.CfnOutput(this, 'BedrockAgentId', { value: agent.agentId });
    new cdk.CfnOutput(this, 'AgentCoreRuntimeArn', { value: agentRuntime.agentRuntimeArn });
    new cdk.CfnOutput(this, 'AgentCoreEndpointArn', { value: agentEndpoint.agentRuntimeEndpointArn });
  }
}

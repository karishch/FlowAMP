/**
 * Normalized multi-platform agent schema.
 *
 * Every agent — whether native (Bedrock/Strands), discovered from
 * Microsoft Copilot Studio, Okta Secure AI, or MuleSoft Agent Fabric —
 * is stored in the same DynamoDB table with a consistent shape.
 *
 * DynamoDB design:
 *   PK: agentId          (string)  — unique across all platforms
 *   GSI1 PK: platform    (string)  — "native" | "microsoft" | "okta" | "mulesoft"
 *   GSI1 SK: category    (string)  — for per-platform + category queries
 */

// ── Supported platforms ──
export type Platform = 'native' | 'microsoft' | 'okta' | 'mulesoft';

// ── Normalized agent record ──
export interface AgentRecord {
  // Identity
  agentId: string;              // PK — e.g. "msft:copilot-invoice-processor"
  name: string;
  platform: Platform;           // GSI1 PK
  platformAgentId?: string;     // original ID on the source platform
  category: string;             // GSI1 SK — "Grid Operations", "IT Helpdesk", etc.
  system: string;               // source system — "GE ADMS", "Copilot Studio", "MuleSoft"

  // Status
  status: 'active' | 'warning' | 'error' | 'inactive' | 'discovered';

  // Performance metrics (normalized across platforms)
  requests: number;
  errors: number;
  avgResponseMs: number;
  utilization: number;          // 0-100

  // Cost
  monthlyCost: number;
  costPerInvocation: number;

  // Responsible AI scores (computed by rai-scorer)
  score: number;
  fairness: number;
  transparency: number;
  accountability: number;
  ethics: number;

  // Discovery metadata
  discoveredAt?: string;        // ISO timestamp of first discovery
  lastSyncedAt?: string;        // ISO timestamp of last sync
  platformMetadata?: Record<string, unknown>; // raw platform-specific data

  // Identity / access (from Okta or native)
  owner?: string;
  accessPolicies?: string[];    // Okta policy IDs or native access keys
}

// ── Discovery sync result ──
export interface DiscoverySyncResult {
  platform: Platform;
  agentsDiscovered: number;
  agentsUpdated: number;
  agentsRemoved: number;
  syncedAt: string;
  errors?: string[];
}

// ── Platform connector config (stored in SSM or env vars) ──
export interface PlatformConnectorConfig {
  platform: Platform;
  enabled: boolean;
  endpoint?: string;            // API base URL
  credentialArn?: string;       // Secrets Manager ARN for API keys
  syncIntervalMinutes: number;  // how often to poll
}

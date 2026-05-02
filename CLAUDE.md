# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Corporate MCP server for **Intune support, troubleshooting, operations, and governance** via Microsoft Graph. Target environment: 10k+ devices. Full spec in `SDD.txt`.

## Planned stack

- **MCP server**: TypeScript/Node.js
- **Auth**: MSAL + client credentials flow (certificate, not secret); workload identity on AKS
- **Infra**: Azure Kubernetes Service, Redis, async queue, Key Vault, OpenTelemetry
- **Reporting workers**: Python optional
- **Graph integration**: `@microsoft/microsoft-graph-client` + MSAL

No code exists yet. When starting implementation, follow the repo structure in SDD.txt §"Estrutura de repositório".

## Architecture: three logical planes

| Plane | Purpose |
|---|---|
| **Transactional** | Device lookup, compliance, inventory, remote actions — near real-time |
| **Configuration** | Policies, remediations, onboarding, RBAC, governance |
| **Reporting** | ExportJobs, Data Warehouse, historical/analytical queries |

All tools route through a central `GraphGateway` — tools never call Graph directly. Gateway owns auth, pagination, retry, batching, caching, throttling budget, masking, and telemetry.

## API versioning rule

**v1.0 by default. Beta only under feature flags with contract tests.**

Beta-only surfaces (require feature flag): `deviceHealthScripts`, `initiateOnDemandProactiveRemediation`, `rotateLocalAdminPassword`, `rotateBitLockerKeys`, `windowsFeatureUpdateProfiles`, `windowsQualityUpdateProfiles`, `windowsDriverUpdateProfiles`, `windowsAutopilotDeploymentProfiles`.

## Graph constraints (hard limits)

- Global throttle: 130,000 req/10s/app — respect `Retry-After` on HTTP 429
- JSON batch: max **20 requests per batch** — enforce at `build_batch()`
- Pagination: always follow `@odata.nextLink`; expose `nextCursor` to callers
- Use `$select`, `$filter`, `$top` on every query
- Prefer delta query for incremental sync; prefer ExportJobs/Data Warehouse over fan-out for reports

## Tool response envelope

Every tool must return this shape:

```json
{
  "status": "ok|partial|error|pending_approval",
  "requestId": "uuid",
  "correlationId": "uuid",
  "data": {},
  "warnings": [],
  "errors": [],
  "meta": {
    "source": "graph|exportJobs|dataWarehouse|cache",
    "apiVersion": "v1.0|beta",
    "cached": false,
    "nextCursor": null
  }
}
```

## Sensitive operations (approval required)

These must go through the approval workflow (`status: "pending_approval"`) and never execute synchronously:

- `request_laps_secret`, `request_laps_rotation`
- `request_bitlocker_key`, `request_bitlocker_rotation`
- `request_wipe`, `request_retire`, `request_delete`
- `request_remediation_run` (privileged)

BitLocker key: value only returned with `$select=key` — generates audit log. LAPS secret requires `DeviceLocalCredential.Read.All`, not just `.ReadBasic.All`.

## Delivery phases

| Phase | Focus |
|---|---|
| **V1** | `search_devices`, `get_device_overview`, `get_compliance_state`, `get_policy_status`, `export_report`, `get_audit_events`, remote actions with governance |
| **V2** | Remediations (beta), Autopilot, update profiles (beta), endpoint security |
| **V3** | Windows Autopatch programmatic, TCM drift, bulk actions, event-driven sync |

## Key Graph permission scopes

| Domain | Minimum scope |
|---|---|
| Device inventory / software | `DeviceManagementManagedDevices.Read.All` |
| Audit events | `DeviceManagementApps.Read.All` |
| Reports / ExportJobs | `DeviceManagementManagedDevices.ReadWrite.All` (or apps/config variant) |
| Scripts / remediations | `DeviceManagementScripts.Read.All` / `ReadWrite.All` |
| Privileged actions | `DeviceManagementManagedDevices.PrivilegedOperations.All` |
| LAPS secret | `DeviceLocalCredential.Read.All` |
| BitLocker key | `BitlockerKey.Read.All` |
| RBAC | `DeviceManagementRBAC.Read.All` |
| Autopilot | `DeviceManagementServiceConfig.Read.All` |
| Windows Autopatch | `WindowsUpdates.Read.All` |

# MCP Intune V1 — Design Spec

**Data:** 2026-05-02  
**Escopo:** V1 local/dev — domínio Device completo  
**Stack:** Python + FastMCP, HTTP+SSE transport  
**Referências:** `mcp-msteams` (padrões corporativos Graph/MSAL), `mcp-meraki`

---

## Decisões de contexto

| Decisão | Escolha | Motivo |
|---|---|---|
| Deploy inicial | Local/dev | Valida funcionamento antes de AKS |
| Auth | Client secret via `.env` | Simplicidade em dev; certificado em produção |
| Transport | HTTP + SSE | Qualquer cliente MCP conecta via URL local |
| Domínio inicial | Device | Maior valor imediato para suporte N2/N3 |
| Testes | Tenant real (integration) + respx (unit) | Validação real sem dependência de mock frágil |
| Versão API | v1.0 por padrão; `/beta` bloqueado por feature flag | Política do SDD |

---

## Arquitetura

### Camadas (5 — padrão mcp-msteams)

```
tools/device/device_tools.py     ← @mcp.tool via _register(mcp), @audited
services/device/device_service.py ← orquestração, composição de respostas
graph/client.py                   ← GraphGateway: httpx, retry, paginação, cache
security/auth.py                  ← MSAL singleton, client credentials
Microsoft Graph API (v1.0)
```

### Fluxo de request

```
Cliente MCP
    │  HTTP POST /messages
    ▼
FastMCP Server (server.py)
    │  despacha tool
    ▼
device_tools.py
    │  valida input (Pydantic)
    │  chama service
    ▼
device_service.py
    │  compõe chamadas Graph
    ▼
graph/client.py (GraphGateway)
    │  cache hit? → retorna
    │  cache miss → GET Graph
    │  429? → retry com Retry-After
    │  nextLink? → pagina até fim
    ▼
Microsoft Graph
    │
    ▼
envelope padrão → render_response(result, ResponseFormat)
    ▼
Cliente MCP
```

---

## Estrutura de pastas

```
mcp-intune/
├── src/mcp_intune/
│   ├── server.py
│   ├── config.py
│   ├── logging_config.py
│   ├── graph/
│   │   ├── client.py
│   │   └── errors.py
│   ├── security/
│   │   └── auth.py
│   ├── tools/
│   │   └── device/
│   │       └── device_tools.py
│   ├── services/
│   │   └── device/
│   │       └── device_service.py
│   ├── schemas/
│   │   ├── requests/
│   │   ├── responses/
│   │   └── entities/
│   └── utils/
│       ├── audit.py
│       ├── render.py
│       └── graph_errors.py
├── tests/
│   ├── conftest.py
│   ├── test_tool_registration.py
│   ├── test_graph_client.py
│   └── test_device_service.py
├── docs/superpowers/specs/
├── .env.example
├── pyproject.toml
└── CLAUDE.md
```

V2/V3 adicionam `tools/reporting/`, `tools/governance/`, `tools/scripts/` etc. com a mesma estrutura — zero refactor no core.

---

## Tools V1 (domínio Device)

Todas com prefixo `intune_`, suporte a `response_format: json|markdown` (padrão `markdown`).

| Tool | Endpoint Graph | Permissão mínima |
|---|---|---|
| `intune_search_devices` | `GET /deviceManagement/managedDevices?$filter=(deviceName|serialNumber|userPrincipalName) eq '...'&$top=N` — busca por nome, serial ou UPN | `DeviceManagementManagedDevices.Read.All` |
| `intune_get_device_overview` | `GET /deviceManagement/managedDevices/{id}` — `include` aceita `["hardware","primaryUser","compliance","policies","detectedApps"]` (cada um dispara sub-call adicional) | `DeviceManagementManagedDevices.Read.All` |
| `intune_get_device_hardware` | `GET /deviceManagement/managedDevices/{id}?$select=manufacturer,model,serialNumber,totalStorageSpaceInBytes,freeStorageSpaceInBytes,physicalMemoryInBytes,hardwareInformation` | `DeviceManagementManagedDevices.Read.All` |
| `intune_get_device_users` | `GET /deviceManagement/managedDevices/{id}/users` | `DeviceManagementManagedDevices.Read.All` |
| `intune_get_detected_apps` | `GET /deviceManagement/managedDevices/{id}/detectedApps` (paginado via nextLink) | `DeviceManagementManagedDevices.Read.All` |
| `intune_get_compliance_state` | `GET /deviceManagement/managedDevices/{id}?$select=complianceState,lastSyncDateTime` + `GET /deviceManagement/managedDevices/{id}/deviceCompliancePolicyStates` | `DeviceManagementManagedDevices.Read.All` |
| `intune_get_policy_status` | `GET /deviceManagement/managedDevices/{id}/deviceConfigurationStates?$filter=state eq 'error'` (ou sem filtro para todas) | `DeviceManagementManagedDevices.Read.All` |

### Envelope de resposta (todas as tools)

```json
{
  "status": "ok|partial|error",
  "requestId": "uuid",
  "correlationId": "uuid",
  "data": {},
  "warnings": [],
  "errors": [],
  "meta": {
    "source": "graph|cache",
    "apiVersion": "v1.0",
    "cached": false,
    "nextCursor": null
  }
}
```

---

## GraphGateway (`graph/client.py`)

```python
graph_get(path, params, ttl)           # GET único recurso com cache TTL
graph_get_all_pages(path, params)      # segue @odata.nextLink até fim
graph_get_paged(path, params, top)     # retorna page + has_more + nextCursor
graph_post(path, body)                 # POST sem cache
build_batch(requests_list)             # valida ≤20, retorna batch payload
```

- `httpx.AsyncClient` global: `connect=10s`, `read=30s`, `pool=5s`, `max_connections=100`
- Retry via `tenacity`: 4 tentativas, backoff exponencial cap 30s, `retry_if_exception_type(ThrottlingError | ServiceUnavailableError)`
- Cache TTL em memória: `asyncio.Lock` por chave (previne stampede)
- `_assert_beta_allowed(path)`: lança `BetaApiNotAllowedError` se `ALLOW_BETA_APIS=false`

### Hierarquia de erros

```
GraphError
├── ThrottlingError          (429 — inclui retry_after_seconds)
├── NotFoundError            (404)
├── AuthError                (401, 403)
├── GraphValidationError     (400)
├── ServiceUnavailableError  (5xx)
└── BetaApiNotAllowedError   (feature flag)
```

---

## Auth (`security/auth.py`)

- `ConfidentialClientApplication` (MSAL) inicializado uma vez com `threading.Lock`
- Scope: `https://graph.microsoft.com/.default`
- `get_token() -> str`: chama `acquire_token_for_client`, lança `AuthError` se falhar
- `client_secret` via `SecretStr` (nunca logado)

---

## Config (`config.py`)

`pydantic-settings BaseSettings`, arquivo `.env`:

```
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=

FASTMCP_TRANSPORT=http
FASTMCP_HOST=127.0.0.1
FASTMCP_PORT=8000

LOG_LEVEL=INFO
ALLOW_BETA_APIS=false

CACHE_TTL_DEVICE=60
CACHE_TTL_POLICY=120
CACHE_TTL_APP=300

GRAPH_TIMEOUT_CONNECT=10
GRAPH_TIMEOUT_READ=30
GRAPH_MAX_RETRIES=4
GRAPH_DEFAULT_TOP=50
```

---

## Observabilidade

- `structlog` com JSON renderer em produção, console em dev (`LOG_FORMAT=console`)
- `@audited` decorator em todas as tools: injeta `trace_id` (8-char UUID) via `ContextVar`
- Logs: `tool_invoked` (params sanitizados), `tool_completed` (elapsed_ms), `tool_failed` (error)
- `graph/client.py` loga: método, path, status_code, elapsed_ms, attempt, cached

---

## Testes

| Arquivo | Cobertura |
|---|---|
| `test_tool_registration.py` | 7 tools com prefixo `intune_` registradas |
| `test_graph_client.py` | retry 429 + Retry-After, paginação nextLink, cache stampede, `build_batch` ≤20 |
| `test_device_service.py` | `search_devices`, `get_device_overview`, `get_compliance_state` com mock via `respx` |

Stack: `pytest` + `pytest-asyncio` (strict) + `respx`.

---

## Dependências (`pyproject.toml`)

```toml
[project]
dependencies = [
  "fastmcp>=2.0",
  "httpx>=0.27",
  "msal>=1.28",
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
  "tenacity>=8.3",
  "structlog>=24.1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
  "respx>=0.21",
  "ruff>=0.4",
  "mypy>=1.10",
]
```

---

## Fora de escopo V1

- Remote actions (request_sync, request_restart, etc.) — V1 é read-only
- Approval workflow — V2
- Redis cache — local usa dict em memória
- AKS / workload identity / Key Vault — produção
- Qualquer endpoint `/beta` — V2 com feature flag habilitado

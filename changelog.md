# Changelog

Todas as mudanças relevantes deste projeto são documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## 2026-05-02 — V2: Ações Remotas, Approval Workflow e Reporting

### Added

- **Ações remotas não-destrutivas** (executam imediatamente)
  - `intune_request_sync`, `intune_request_restart`, `intune_request_scan`, `intune_request_locate`

- **Ações destrutivas com approval workflow**
  - `intune_request_retire`, `intune_request_wipe`, `intune_request_delete` — retornam `status: pending_approval`
  - `intune_list_pending_actions`, `intune_approve_action`, `intune_deny_action`, `intune_execute_action`
  - Approval store in-memory com TTL configurável (`APPROVAL_TTL_SECONDS`, padrão 3600s)

- **Reporting (ExportJobs)**: `intune_export_report`, `intune_get_report_status`, `intune_list_report_catalog`

- **Auditoria**: `intune_get_audit_events` — eventos com filtro por período, ator e categoria

- **Endpoint Analytics**: `intune_get_endpoint_analytics` — scores de startup, app reliability, work from anywhere

- `graph_delete` helper + `_do_request` agora retorna `{}` para respostas 204 No Content

### Changed

- **Total de tools expostas: 23** (era 7 na V1)
- `config.py`: campo `APPROVAL_TTL_SECONDS` adicionado

---

## 2026-05-02

### Added

- **V1 inicial — domínio de dispositivos**  
  Implementação completa do servidor MCP com 7 tools de leitura para o domínio de dispositivos Intune.

- **`intune_search_devices`**  
  Busca dispositivos por prefixo de nome, número de série (exato) ou UPN (exato). Suporta filtro por plataforma e estado de compliance. Usa OData `$filter` com escaping de aspas simples para prevenir injeção.

- **`intune_get_device_overview`**  
  Snapshot combinado do dispositivo com controle de seções via parâmetro `include`. Busca concorrente de usuário primário, compliance e políticas via `asyncio.gather`.

- **`intune_get_device_hardware`**  
  Inventário de hardware com `$select` restrito a campos de especificação física.

- **`intune_get_device_users`**  
  Usuários associados ao dispositivo via endpoint `/users`.

- **`intune_get_detected_apps`**  
  Lista completa de softwares detectados com paginação automática via `@odata.nextLink`.

- **`intune_get_compliance_state`**  
  Estado de compliance do dispositivo e resultado por política de compliance. Busca concorrente do dispositivo e das policy states via `asyncio.gather`.

- **`intune_get_policy_status`**  
  Estado de atribuição de políticas de configuração com filtro opcional por tipo de plataforma.

- **GraphGateway (`graph/client.py`)**  
  Cliente httpx assíncrono com singleton lazy, cache TTL por chave com prevenção de stampede via `asyncio.Lock`, retry via `tenacity` com backoff exponencial e respeito ao header `Retry-After`, paginação completa e helper de batch.

- **Autenticação MSAL (`security/auth.py`)**  
  Singleton com `threading.Lock` e double-checked locking para client credentials flow.

- **Hierarquia de erros Graph (`graph/errors.py`)**  
  `ThrottlingError`, `NotFoundError`, `AuthError`, `GraphValidationError`, `ServiceUnavailableError`, `BetaApiNotAllowedError`.

- **Decorator `@audited` (`utils/audit.py`)**  
  Execution logging com `trace_id` via `ContextVar`, reset correto via token.

- **Configuração via pydantic-settings (`config.py`)**  
  Todas as variáveis de ambiente com valores padrão, `SecretStr` para client secret, `ALLOW_BETA_APIS` como feature flag.

- **Logging estruturado (`logging_config.py`)**  
  structlog com renderização JSON (produção) ou console (desenvolvimento).

- **38 testes unitários**  
  Cobertura de client Graph (cache, retry, paginação, batch, erros), auth, serviço de dispositivos e registro de tools.

---

### Changed

- **API versioning**: v1.0 por padrão. Beta bloqueado via `BetaApiNotAllowedError` salvo `ALLOW_BETA_APIS=true`.

- **Cache key normalizada via httpx**: uso de `build_request().url` para garantir encoding consistente de parâmetros OData.

- **Timestamp fresco dentro do lock**: `time.monotonic()` recalculado dentro do `asyncio.Lock` para evitar falso cache hit após suspensão longa.

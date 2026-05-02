# MCP Intune

Servidor MCP para suporte, troubleshooting e operações do Microsoft Intune. Consulte dispositivos, compliance, políticas, aplicativos instalados e usuários via Microsoft Graph API. Projetado para diagnósticos de suporte e governança de endpoints. Zero operações de escrita na V1.

## 📂 Estrutura de Pastas

```text
mcp-intune/
├── src/
│   └── mcp_intune/            # Pacote principal
│       ├── graph/             # Abstração da API Microsoft Graph (cliente, cache, retry)
│       ├── tools/             # Definições de ferramentas MCP categorizadas por domínio
│       ├── services/          # Camada de lógica de negócio entre ferramentas e API
│       ├── schemas/           # Modelos Pydantic para validação de dados
│       ├── security/          # Gestão de autenticação e tokens (MSAL)
│       ├── utils/             # Funções utilitárias comuns
│       ├── server.py          # Ponto de entrada e registro do servidor MCP
│       ├── config.py          # Gestão de configuração e ambiente
│       └── logging_config.py  # Configuração de logging estruturado (structlog)
├── tests/                     # Testes unitários e de integração
├── docs/                      # Documentação detalhada e guias
├── .env.example               # Exemplo de configuração local
├── pyproject.toml             # Metadados do projeto e dependências
├── readme.md                  # Este arquivo
└── changelog.md               # Histórico consolidado de mudanças
```

## 🏗️ Arquitetura

O projeto segue uma arquitetura em camadas, pensada para modularidade, clareza e baixo acoplamento:

1. **Ponto de entrada (`server.py`)**  
   Inicializa o servidor `FastMCP` e registra apenas as tools expostas publicamente.

2. **Camada de interface (`tools/`)**  
   Define as ferramentas visíveis ao LLM, com docstrings operacionais, validação de parâmetros e renderização da resposta.

3. **Camada de serviço (`services/`)**  
   Orquestra a lógica de negócio. Toda agregação, transformação e composição de chamadas Graph acontece aqui.

4. **Camada de API (`graph/`)**  
   Abstração sobre a Microsoft Graph API com cliente `httpx` assíncrono, paginação, retry e cache TTL por domínio.

5. **Segurança (`security/`)**  
   Autenticação app-only via MSAL com client credentials flow (client secret ou certificado).

6. **Resiliência**  
   Uso de `tenacity` para retry com backoff exponencial. Throttling com `Retry-After` respeitado. Cache TTL com prevenção de cache stampede via `asyncio.Lock` por chave.

## 🛠️ Referência de Ferramentas

Todas as ferramentas são apenas de **leitura** na V1.  
Total atual: **34 ferramentas**.

### 💻 Dispositivos

- **`intune_search_devices`**: busca dispositivos por prefixo de nome, número de série (exato) ou UPN (exato). **Use esta ferramenta primeiro** para identificar um dispositivo antes de qualquer outra consulta. Suporta filtro por plataforma e estado de compliance.

- **`intune_get_device_overview`**: snapshot combinado do dispositivo com usuário primário, compliance e políticas em uma única chamada. Aceita `include` para controlar quais seções são retornadas.

- **`intune_get_device_hardware`**: inventário de hardware — modelo, número de série, armazenamento total/livre e RAM.

- **`intune_get_device_users`**: usuários associados ao dispositivo (usuário primário e usuários logados).

- **`intune_get_detected_apps`**: lista completa de softwares detectados no dispositivo (paginação automática). Pode retornar centenas de itens.

- **`intune_get_compliance_state`**: estado de compliance e lista de políticas de compliance com resultado por política (`compliant`, `nonCompliant`, `error`). Ideal para diagnóstico de não conformidade.

- **`intune_get_policy_status`**: estado de atribuição de políticas de configuração por dispositivo. Suporta filtro por tipo de plataforma. **Não use** para políticas de compliance — use `intune_get_compliance_state`.

### ⚡ Ações Remotas

- **`intune_request_sync`**: forçar sincronização de políticas (executa imediatamente).
- **`intune_request_restart`**: reiniciar dispositivo remotamente (executa imediatamente).
- **`intune_request_scan`**: iniciar varredura do Windows Defender — quick ou full scan (executa imediatamente).
- **`intune_request_locate`**: solicitar localização do dispositivo (executa imediatamente, dispositivo deve estar online).
- **`intune_request_retire`**: retire com remoção de dados corporativos. **Requer aprovação** — retorna `pending_approval`.
- **`intune_request_wipe`**: wipe factory reset. **Requer aprovação** — retorna `pending_approval`.
- **`intune_request_delete`**: exclusão do registro no Intune. **Requer aprovação** — retorna `pending_approval`.
- **`intune_list_pending_actions`**: lista ações destrutivas aguardando aprovação.
- **`intune_approve_action`**: aprova ação pendente (não executa — use `intune_execute_action` em seguida).
- **`intune_deny_action`**: rejeita ação pendente.
- **`intune_execute_action`**: executa ação aprovada contra o Graph. Falha se não estiver aprovada.

### 📊 Relatórios e Auditoria

- **`intune_export_report`**: cria ExportJob assíncrono. Retorna `jobId` para polling. Use `intune_list_report_catalog` primeiro.
- **`intune_get_report_status`**: verifica status do ExportJob. Quando `completed`, `downloadUrl` disponível.
- **`intune_list_report_catalog`**: lista relatórios disponíveis para `intune_export_report`.
- **`intune_get_audit_events`**: eventos de auditoria — quem fez o quê, quando. Filtra por ator, categoria e período.
- **`intune_get_endpoint_analytics`**: scores de Endpoint Analytics (startup, app reliability, work from anywhere).

### 🔧 Remediações (Proativas)

- **`intune_list_remediations`**: lista scripts de remediação proativa (deviceHealthScripts). Requer `ALLOW_BETA_APIS=true`.
- **`intune_get_remediation_run_state`**: estado de execução de um script por dispositivo. Requer `ALLOW_BETA_APIS=true`.
- **`intune_request_remediation_run`**: execução on-demand de remediação. **Requer aprovação** + `ALLOW_BETA_APIS=true`.

### 🔄 Atualizações Windows

- **`intune_list_update_rings`**: lista update rings WUfB com deferral e pause status (v1.0).
- **`intune_get_update_ring`**: detalhes de um ring com grupos atribuídos (v1.0).
- **`intune_list_feature_update_profiles`**: perfis de versão alvo de feature update. Requer `ALLOW_BETA_APIS=true`.
- **`intune_list_quality_update_profiles`**: perfis de patch mensal. Requer `ALLOW_BETA_APIS=true`.
- **`intune_list_driver_update_profiles`**: perfis de atualização de drivers. Requer `ALLOW_BETA_APIS=true`.

### 🚀 Autopilot

- **`intune_list_autopilot_devices`**: lista identidades Autopilot com status de atribuição de perfil.
- **`intune_get_autopilot_device_by_serial`**: encontra dispositivo Autopilot por número de série.
- **`intune_import_autopilot_device`**: importa novo dispositivo para Autopilot via hardware hash.

## 💻 Stack Tecnológica

| Camada | Tecnologia |
|--------|------------|
| Linguagem | Python 3.12+ |
| MCP Server | FastMCP |
| HTTP Client | httpx assíncrono com pool de conexões |
| Autenticação | MSAL Python |
| Validação | Pydantic v2 |
| Resiliência | tenacity |
| Logging | structlog |
| Testes | pytest |
| Linting | Ruff |

## 🚀 Configuração

### Pré-requisitos

- Registro de aplicativo no Azure com **Permissões de Aplicativo** no Microsoft Graph
- `Client ID`
- `Client Secret`
- `Tenant ID`

### Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
Copy-Item .env.example .env
```

### Executando o servidor

```powershell
python -m mcp_intune.server
```

Endpoint padrão:

- `http://127.0.0.1:8000/mcp`

## 🔧 Configuração de Ambiente

Variáveis principais em `.env`:

- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `FASTMCP_TRANSPORT`
- `FASTMCP_HOST`
- `FASTMCP_PORT`
- `LOG_LEVEL`
- `LOG_FORMAT`

Controles operacionais:

- `ALLOW_BETA_APIS` — habilita endpoints `/beta` do Graph (padrão: `false`)
- `CACHE_TTL_DEVICE` — TTL de cache para dados de dispositivo em segundos (padrão: `60`)
- `CACHE_TTL_POLICY` — TTL de cache para dados de política em segundos (padrão: `120`)
- `CACHE_TTL_APP` — TTL de cache para dados de aplicativo em segundos (padrão: `300`)
- `GRAPH_DEFAULT_TOP` — tamanho padrão de página nas consultas Graph (padrão: `50`)
- `GRAPH_MAX_RETRIES` — tentativas máximas em erros transitórios (padrão: `4`)

## 🔑 Permissões Graph

Permissões de aplicativo necessárias:

| Permissão | Propósito |
|-----------|-----------|
| `DeviceManagementManagedDevices.Read.All` | Inventário de dispositivos e software |
| `DeviceManagementConfiguration.Read.All` | Políticas de configuração |
| `DeviceManagementManagedDevices.ReadWrite.All` | ExportJobs e relatórios |
| `DeviceManagementApps.Read.All` | Eventos de auditoria |
| `DeviceManagementManagedDevices.PrivilegedOperations.All` | Ações remotas (retire, wipe) |
| `DeviceManagementScripts.Read.All` | Scripts e remediações |
| `DeviceManagementServiceConfig.Read.All` | Autopilot |

## ⚠️ Limitações Conhecidas

- **V1 somente leitura**: operações de escrita, ações remotas e remediações estão planejadas para V2.
- **Beta APIs desabilitadas por padrão**: endpoints `/beta` requerem `ALLOW_BETA_APIS=true` e feature flags explícitas.
- **Paginação de apps detectados**: `intune_get_detected_apps` busca todas as páginas em sequência — pode ser lento em dispositivos com muitos softwares.
- **Cache por TTL**: dados de dispositivo têm TTL de 60s. Para dados em tempo real após ação manual no portal, aguarde expiração do cache ou reinicie o servidor.
- **JSON batch**: o cliente suporta batch de até 20 requisições por chamada (limite do Graph).
- **Graph API throttling**: limite global de 130.000 req/10s/app. O cliente respeita `Retry-After` automaticamente.

## 🩺 Troubleshooting

- **403 em qualquer tool**: verifique se o app registration tem `DeviceManagementManagedDevices.Read.All` como permissão de aplicativo (não delegada) e se o admin grant foi concedido.
- **429 no Graph**: o cliente já faz retry com backoff. Se persistir, reduza `GRAPH_DEFAULT_TOP` ou adicione delay entre chamadas.
- **Logging de produção**: formato padrão é JSON via `LOG_FORMAT=json`. Use `console` apenas para depuração local.
- **404 em `.well-known/oauth-authorization-server`**: esperado quando o cliente faz probe OAuth e o servidor MCP não expõe discovery.
- **Catálogo de tools desatualizado**: reinicie a sessão MCP/Portal.

## ✅ Testes

```powershell
pytest tests -v
```

Se o ambiente local não resolver o pacote `mcp_intune`, execute com `PYTHONPATH=src`.

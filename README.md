# Openprovider MCP Server

An [MCP](https://modelcontextprotocol.io/) server that exposes the [Openprovider](https://www.openprovider.com/) domain registrar API as tools for Claude Code and other MCP-compatible clients.

Manage domains, DNS zones, nameservers, SSL certificates, WHOIS contacts, customers, and billing — all from your AI assistant.

## Prerequisites

- Python 3.10+
- An [Openprovider](https://www.openprovider.com/) reseller account
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (or any MCP client)

## Setup

```bash
git clone https://github.com/civiqsai/openprovider-mcp.git
cd openprovider-mcp
bash install.sh
```

The installer creates a virtual environment, installs dependencies, prompts for your Openprovider credentials, and optionally registers the server in Claude Code.

### Manual setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Openprovider username and password
chmod 600 .env
claude mcp add -s user -t stdio openprovider -- "$(pwd)/.venv/bin/python" "$(pwd)/server.py"
```

## Multiple accounts

The server supports managing domains across multiple Openprovider reseller accounts.

### Configuration

Use the naming convention `OPENPROVIDER_{NAME}_USERNAME` / `OPENPROVIDER_{NAME}_PASSWORD` in your `.env`:

```env
OPENPROVIDER_MYCOMPANY_USERNAME=user1
OPENPROVIDER_MYCOMPANY_PASSWORD=pass1

OPENPROVIDER_OTHERACCOUNT_USERNAME=user2
OPENPROVIDER_OTHERACCOUNT_PASSWORD=pass2
```

The legacy single-account format (`OPENPROVIDER_USERNAME` / `OPENPROVIDER_PASSWORD`) is still supported and creates an account named "default".

### Switching accounts

```
openprovider_list_accounts        → shows available accounts and which is active
openprovider_select_account("x")  → switches all subsequent calls to account "x"
openprovider_whoami               → verify you're on the right account
```

The first account alphabetically is active at startup.

## Tools

52 tools organized by category. All list endpoints support `limit`/`offset` pagination (default limit=100).

### Account management

| Tool | Description |
|------|-------------|
| `openprovider_list_accounts` | List configured accounts and show which is active |
| `openprovider_select_account` | Switch the active account |
| `openprovider_whoami` | Show reseller account info (company, balance, settings) |
| `openprovider_get_reseller_by_id` | Get reseller details by ID |

### Domains

| Tool | Description |
|------|-------------|
| `openprovider_list_domains` | List domains with filters (extension, status, name pattern) |
| `openprovider_get_domain` | Get full domain details by ID |
| `openprovider_check_domain` | Check domain availability |
| `openprovider_get_domain_price` | Get pricing for create/transfer/renew/restore |
| `openprovider_create_domain` | Register a new domain |
| `openprovider_transfer_domain` | Transfer a domain to Openprovider |
| `openprovider_trade_domain` | Change domain registrant |
| `openprovider_update_domain` | Update domain settings |
| `openprovider_renew_domain` | Renew a domain |
| `openprovider_delete_domain` | Cancel a domain registration |
| `openprovider_restore_domain` | Restore a deleted domain (grace period) |
| `openprovider_get_authcode` | Get transfer/auth code |
| `openprovider_reset_authcode` | Regenerate auth code |

### TLDs

| Tool | Description |
|------|-------------|
| `openprovider_list_tlds` | List available TLD extensions |
| `openprovider_get_tld` | Get TLD details |

### DNS zones

| Tool | Description |
|------|-------------|
| `openprovider_list_dns_zones` | List DNS zones |
| `openprovider_get_dns_zone` | Get zone with all records |
| `openprovider_create_dns_zone` | Create a new zone |
| `openprovider_update_dns_zone` | Update a zone (replaces all records) |
| `openprovider_delete_dns_zone` | Delete a zone |
| `openprovider_list_dns_records` | List records for a zone |

### Nameservers

| Tool | Description |
|------|-------------|
| `openprovider_list_nameservers` | List nameservers |
| `openprovider_get_nameserver` | Get nameserver details |
| `openprovider_create_nameserver` | Create a nameserver |
| `openprovider_update_nameserver` | Update a nameserver |
| `openprovider_delete_nameserver` | Delete a nameserver |

### Nameserver groups

| Tool | Description |
|------|-------------|
| `openprovider_list_ns_groups` | List nameserver groups |
| `openprovider_get_ns_group` | Get group details |
| `openprovider_create_ns_group` | Create a nameserver group |
| `openprovider_update_ns_group` | Update a nameserver group |
| `openprovider_delete_ns_group` | Delete a nameserver group |

### DNS templates

| Tool | Description |
|------|-------------|
| `openprovider_list_dns_templates` | List DNS templates |
| `openprovider_get_dns_template` | Get template by ID |
| `openprovider_create_dns_template` | Create a DNS template |
| `openprovider_delete_dns_template` | Delete a DNS template |

### SSL certificates

| Tool | Description |
|------|-------------|
| `openprovider_list_ssl_orders` | List SSL orders |
| `openprovider_get_ssl_order` | Get order details |
| `openprovider_create_ssl_order` | Order an SSL certificate |
| `openprovider_update_ssl_order` | Update an order |
| `openprovider_cancel_ssl_order` | Cancel an order |
| `openprovider_reissue_ssl_order` | Reissue a certificate |
| `openprovider_resend_ssl_email` | Resend validation email |

### WHOIS contacts

| Tool | Description |
|------|-------------|
| `openprovider_list_contacts` | List contacts |
| `openprovider_get_contact` | Get contact details |
| `openprovider_create_contact` | Create a contact |
| `openprovider_update_contact` | Update a contact |
| `openprovider_delete_contact` | Delete a contact |

### Customers

| Tool | Description |
|------|-------------|
| `openprovider_list_customers` | List reseller customers |
| `openprovider_get_customer` | Get customer details |
| `openprovider_create_customer` | Create a customer |
| `openprovider_update_customer` | Update a customer |
| `openprovider_delete_customer` | Delete a customer |

### Billing (read-only)

| Tool | Description |
|------|-------------|
| `openprovider_list_invoices` | List invoices |
| `openprovider_get_invoice` | Get invoice details |
| `openprovider_list_payments` | List payments |
| `openprovider_get_payment` | Get payment details |

## Operational warnings

### Cost

Domain registration, renewal, transfer, SSL certificate orders, and domain restores cost real money. The MCP server instructions tell your AI assistant to confirm with you before executing these, but always double-check.

### DNS zone updates replace all records

`openprovider_update_dns_zone` does a full PUT — it replaces the entire record set. Always:

1. GET the current zone first
2. Modify the records array
3. PUT back the complete set

Forgetting this deletes all existing records.

### DNSSEC and nameserver migration

When migrating nameservers away from Openprovider (e.g., to Cloudflare):

1. Disable DNSSEC first — old DS records at the TLD will block resolution if NS points elsewhere
2. Update nameservers to the new provider
3. Wait for the new provider to activate the zone (1-24h for DS records to clear)
4. Enable DNSSEC at the new provider
5. Add the new DS record back via `openprovider_update_domain`

Never migrate nameservers while DNSSEC is active with the old provider's keys.

## Architecture

Two Python files:

- **`server.py`** — FastMCP server with 52 tool definitions (50 API tools + 2 account management). Each tool maps to one Openprovider API endpoint with JSON serialization and error handling.
- **`openprovider.py`** — HTTP client wrapping the Openprovider REST API. Handles authentication (username/password → Bearer token), automatic token refresh (48h TTL, refreshes 1h early), and 401 retry.

The server runs via stdio transport — Claude Code spawns it as a subprocess and communicates over stdin/stdout.

## License

MIT — see [LICENSE](LICENSE).

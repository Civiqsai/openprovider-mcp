"""Openprovider MCP Server — exposes the Openprovider domain registrar API as MCP tools."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load .env from the same directory as this script
load_dotenv(Path(__file__).parent / ".env")

from openprovider import OpenproviderClient, OpenproviderError

# --- Init ---
username = os.environ.get("OPENPROVIDER_USERNAME")
password = os.environ.get("OPENPROVIDER_PASSWORD")
if not username or not password:
    print("OPENPROVIDER_USERNAME and OPENPROVIDER_PASSWORD must be set in .env", file=sys.stderr)
    sys.exit(1)

client = OpenproviderClient(username, password)

mcp = FastMCP(
    "Openprovider",
    instructions=(
        "Openprovider is a domain registrar and hosting platform. "
        "This server provides tools to manage domains, DNS zones, nameservers, "
        "SSL certificates, WHOIS contacts, customers, invoices, and payments. "
        "IMPORTANT: Domain registration, renewal, transfer, and SSL orders cost money — "
        "always confirm with the operator before executing. "
        "DNS zone updates (PUT) replace ALL records — always GET first, modify, then PUT back."
    ),
)


def _err(e: OpenproviderError) -> str:
    return json.dumps({"error": str(e), "status_code": e.status_code, "details": e.body}, ensure_ascii=False)


def _ok(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


# ============================================================
# Reseller / Account
# ============================================================

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_whoami() -> str:
    """Show the reseller account information (company, balance, settings)."""
    try:
        return _ok(client.get("/resellers"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_reseller_by_id(id: int) -> str:
    """Get reseller details by ID."""
    try:
        return _ok(client.get(f"/resellers/{id}"))
    except OpenproviderError as e:
        return _err(e)


# ============================================================
# Domains
# ============================================================

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_list_domains(
    limit: int = 100,
    offset: int = 0,
    extension: str | None = None,
    status: str | None = None,
    name_pattern: str | None = None,
    with_additional_data: bool = False,
) -> str:
    """List domains in the account. Filter by extension (e.g. 'nl'), status (ACT/DEL/PEN/REQ/RRQ/SCR/FAI), or name_pattern."""
    params: dict = {"limit": limit, "offset": offset}
    if extension:
        params["extension"] = extension
    if status:
        params["status"] = status
    if name_pattern:
        params["name_pattern"] = name_pattern
    if with_additional_data:
        params["with_additional_data"] = True
    try:
        return _ok(client.get("/domains", params))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_domain(id: int) -> str:
    """Get full details of a domain by its Openprovider ID."""
    try:
        return _ok(client.get(f"/domains/{id}"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_check_domain(domains: str) -> str:
    """Check domain availability. Pass domains as JSON array of objects:
    [{"name": "example", "extension": "nl"}, {"name": "example", "extension": "com"}]"""
    try:
        data = json.loads(domains)
        return _ok(client.post("/domains/check", {"domains": data}))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_domain_price(
    extension: str,
    operation: str = "create",
) -> str:
    """Get domain price for an extension. Operation: create, transfer, renew, restore."""
    try:
        return _ok(client.get("/domains/prices", {"extension": extension, "operation": operation}))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_create_domain(domain_data: str) -> str:
    """Register a new domain. COSTS MONEY — confirm with operator first.
    Pass domain_data as JSON string. Required fields:
    - domain: {"name": "example", "extension": "nl"}
    - period: int (years)
    - owner_handle, admin_handle, tech_handle, billing_handle: contact handles
    - ns_group or name_servers: nameserver config
    Optional: autorenew (on/off/default), dnssec_keys, additional_data"""
    try:
        data = json.loads(domain_data)
        return _ok(client.post("/domains", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_transfer_domain(transfer_data: str) -> str:
    """Transfer a domain to Openprovider. COSTS MONEY — confirm with operator first.
    Pass transfer_data as JSON string. Required: domain, period, auth_code,
    owner_handle, admin_handle, tech_handle, billing_handle, ns_group or name_servers."""
    try:
        data = json.loads(transfer_data)
        return _ok(client.post("/domains/transfer", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_trade_domain(trade_data: str) -> str:
    """Trade (change registrant of) a domain. May cost money — confirm with operator.
    Pass trade_data as JSON string. Required: domain, period, owner_handle."""
    try:
        data = json.loads(trade_data)
        return _ok(client.post("/domains/trade", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def openprovider_update_domain(id: int, updates: str) -> str:
    """Update domain settings. Pass updates as JSON string.
    Fields: autorenew, ns_group, name_servers, owner_handle, admin_handle,
    tech_handle, billing_handle, dnssec_keys, is_private_whois_enabled, etc."""
    try:
        data = json.loads(updates)
        return _ok(client.put(f"/domains/{id}", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_renew_domain(id: int, period: int = 1) -> str:
    """Renew a domain. COSTS MONEY — confirm with operator first.
    Period in years (default 1)."""
    try:
        return _ok(client.post(f"/domains/{id}/renew", {"period": period}))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
def openprovider_delete_domain(id: int) -> str:
    """Delete/cancel a domain registration. This is destructive — confirm with operator first."""
    try:
        return _ok(client.delete(f"/domains/{id}"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_restore_domain(id: int) -> str:
    """Restore a deleted domain (within grace period). COSTS MONEY — confirm with operator."""
    try:
        return _ok(client.post(f"/domains/{id}/restore"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_authcode(id: int) -> str:
    """Get the auth/transfer code for a domain."""
    try:
        return _ok(client.get(f"/domains/{id}/authcode"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_reset_authcode(id: int) -> str:
    """Reset/regenerate the auth code for a domain."""
    try:
        return _ok(client.post(f"/domains/{id}/authcode/reset"))
    except OpenproviderError as e:
        return _err(e)


# ============================================================
# TLDs
# ============================================================

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_list_tlds(
    limit: int = 100,
    offset: int = 0,
    name_pattern: str | None = None,
    with_price: bool = False,
) -> str:
    """List available TLD extensions. Filter by name_pattern (e.g. 'nl')."""
    params: dict = {"limit": limit, "offset": offset}
    if name_pattern:
        params["name_pattern"] = name_pattern
    if with_price:
        params["with_price"] = True
    try:
        return _ok(client.get("/tlds", params))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_tld(extension: str) -> str:
    """Get details of a specific TLD extension (e.g. 'nl', 'com')."""
    try:
        return _ok(client.get(f"/tlds/{extension}"))
    except OpenproviderError as e:
        return _err(e)


# ============================================================
# DNS Zones
# ============================================================

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_list_dns_zones(
    limit: int = 100,
    offset: int = 0,
    name_pattern: str | None = None,
) -> str:
    """List DNS zones."""
    params: dict = {"limit": limit, "offset": offset}
    if name_pattern:
        params["name_pattern"] = name_pattern
    try:
        return _ok(client.get("/dns/zones", params))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_dns_zone(name: str) -> str:
    """Get a DNS zone with all its records. Name is the domain (e.g. 'example.nl')."""
    try:
        return _ok(client.get(f"/dns/zones/{name}"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_create_dns_zone(zone_data: str) -> str:
    """Create a new DNS zone. Pass zone_data as JSON string.
    Required: domain ({"name": "example", "extension": "nl"}).
    Optional: type (master/slave), records array, template_name."""
    try:
        data = json.loads(zone_data)
        return _ok(client.post("/dns/zones", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def openprovider_update_dns_zone(name: str, zone_data: str) -> str:
    """Update a DNS zone. WARNING: This REPLACES all records — always GET first, modify, then PUT back.
    Pass zone_data as JSON string with 'records' array containing ALL desired records.
    Each record: {"type": "A", "name": "www", "value": "1.2.3.4", "ttl": 3600, "prio": 0}"""
    try:
        data = json.loads(zone_data)
        return _ok(client.put(f"/dns/zones/{name}", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
def openprovider_delete_dns_zone(name: str) -> str:
    """Delete a DNS zone. This removes all records — confirm with operator first."""
    try:
        return _ok(client.delete(f"/dns/zones/{name}"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_list_dns_records(
    name: str,
    limit: int = 100,
    offset: int = 0,
    record_type: str | None = None,
) -> str:
    """List DNS records for a zone. Optionally filter by record_type (A, AAAA, CNAME, MX, TXT, etc.)."""
    params: dict = {"limit": limit, "offset": offset}
    if record_type:
        params["type"] = record_type
    try:
        return _ok(client.get(f"/dns/zones/{name}/records", params))
    except OpenproviderError as e:
        return _err(e)


# ============================================================
# Nameservers
# ============================================================

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_list_nameservers(
    limit: int = 100,
    offset: int = 0,
    name_pattern: str | None = None,
) -> str:
    """List nameservers."""
    params: dict = {"limit": limit, "offset": offset}
    if name_pattern:
        params["name_pattern"] = name_pattern
    try:
        return _ok(client.get("/dns/nameservers", params))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_nameserver(name: str) -> str:
    """Get nameserver details by name."""
    try:
        return _ok(client.get(f"/dns/nameservers/{name}"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_create_nameserver(ns_data: str) -> str:
    """Create a nameserver. Pass ns_data as JSON string.
    Required: name, ip (for glue records). Optional: ip6."""
    try:
        data = json.loads(ns_data)
        return _ok(client.post("/dns/nameservers", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def openprovider_update_nameserver(name: str, ns_data: str) -> str:
    """Update a nameserver. Pass ns_data as JSON string with fields to change."""
    try:
        data = json.loads(ns_data)
        return _ok(client.put(f"/dns/nameservers/{name}", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
def openprovider_delete_nameserver(name: str) -> str:
    """Delete a nameserver."""
    try:
        return _ok(client.delete(f"/dns/nameservers/{name}"))
    except OpenproviderError as e:
        return _err(e)


# ============================================================
# Nameserver Groups
# ============================================================

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_list_ns_groups(
    limit: int = 100,
    offset: int = 0,
    name_pattern: str | None = None,
) -> str:
    """List nameserver groups."""
    params: dict = {"limit": limit, "offset": offset}
    if name_pattern:
        params["name_pattern"] = name_pattern
    try:
        return _ok(client.get("/dns/nameservers/groups", params))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_ns_group(ns_group: str) -> str:
    """Get nameserver group details by name."""
    try:
        return _ok(client.get(f"/dns/nameservers/groups/{ns_group}"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_create_ns_group(group_data: str) -> str:
    """Create a nameserver group. Pass group_data as JSON string.
    Required: ns_group (name), name_servers (array of nameserver objects)."""
    try:
        data = json.loads(group_data)
        return _ok(client.post("/dns/nameservers/groups", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def openprovider_update_ns_group(ns_group: str, group_data: str) -> str:
    """Update a nameserver group. Pass group_data as JSON string."""
    try:
        data = json.loads(group_data)
        return _ok(client.put(f"/dns/nameservers/groups/{ns_group}", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
def openprovider_delete_ns_group(ns_group: str) -> str:
    """Delete a nameserver group."""
    try:
        return _ok(client.delete(f"/dns/nameservers/groups/{ns_group}"))
    except OpenproviderError as e:
        return _err(e)


# ============================================================
# DNS Templates
# ============================================================

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_list_dns_templates(
    limit: int = 100,
    offset: int = 0,
) -> str:
    """List DNS templates."""
    try:
        return _ok(client.get("/dns/templates", {"limit": limit, "offset": offset}))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_dns_template(id: int) -> str:
    """Get a DNS template by ID."""
    try:
        return _ok(client.get(f"/dns/templates/{id}"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_create_dns_template(template_data: str) -> str:
    """Create a DNS template. Pass template_data as JSON string.
    Required: name, records (array of record objects)."""
    try:
        data = json.loads(template_data)
        return _ok(client.post("/dns/templates", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
def openprovider_delete_dns_template(id: int) -> str:
    """Delete a DNS template by ID."""
    try:
        return _ok(client.delete(f"/dns/templates/{id}"))
    except OpenproviderError as e:
        return _err(e)


# ============================================================
# SSL Certificates
# ============================================================

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_list_ssl_orders(
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
) -> str:
    """List SSL certificate orders. Filter by status."""
    params: dict = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    try:
        return _ok(client.get("/ssl", params))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_ssl_order(id: int) -> str:
    """Get SSL order details by ID."""
    try:
        return _ok(client.get(f"/ssl/{id}"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_create_ssl_order(ssl_data: str) -> str:
    """Create an SSL certificate order. COSTS MONEY — confirm with operator first.
    Pass ssl_data as JSON string. Required: product_id, period, csr,
    domain_names_count, approver_email or approver_method, admin_handle, tech_handle."""
    try:
        data = json.loads(ssl_data)
        return _ok(client.post("/ssl", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def openprovider_update_ssl_order(id: int, updates: str) -> str:
    """Update an SSL order. Pass updates as JSON string."""
    try:
        data = json.loads(updates)
        return _ok(client.put(f"/ssl/{id}", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
def openprovider_cancel_ssl_order(id: int) -> str:
    """Cancel an SSL certificate order."""
    try:
        return _ok(client.delete(f"/ssl/{id}"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_reissue_ssl_order(id: int, reissue_data: str) -> str:
    """Reissue an SSL certificate. Pass reissue_data as JSON string with new CSR etc."""
    try:
        data = json.loads(reissue_data)
        return _ok(client.post(f"/ssl/{id}/reissue", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_resend_ssl_email(id: int) -> str:
    """Resend the SSL approval/validation email."""
    try:
        return _ok(client.post(f"/ssl/{id}/resend-email"))
    except OpenproviderError as e:
        return _err(e)


# ============================================================
# Contacts (WHOIS)
# ============================================================

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_list_contacts(
    limit: int = 100,
    offset: int = 0,
    last_name_pattern: str | None = None,
    company_name_pattern: str | None = None,
    role: str | None = None,
) -> str:
    """List WHOIS contacts. Filter by last_name_pattern, company_name_pattern, or role (registrant/admin/tech/billing)."""
    params: dict = {"limit": limit, "offset": offset}
    if last_name_pattern:
        params["last_name_pattern"] = last_name_pattern
    if company_name_pattern:
        params["company_name_pattern"] = company_name_pattern
    if role:
        params["role"] = role
    try:
        return _ok(client.get("/contacts", params))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_contact(id: int) -> str:
    """Get WHOIS contact details by ID (returns handle)."""
    try:
        return _ok(client.get(f"/contacts/{id}"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_create_contact(contact_data: str) -> str:
    """Create a WHOIS contact. Pass contact_data as JSON string.
    Required: name ({"first_name": "...", "last_name": "..."}),
    address ({"street": "...", "number": "...", "zipcode": "...", "city": "...", "country": "NL"}),
    phone ({"country_code": "+31", "area_code": "6", "subscriber_number": "12345678"}),
    email. Optional: company_name, vat (for companies), fax."""
    try:
        data = json.loads(contact_data)
        return _ok(client.post("/contacts", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def openprovider_update_contact(id: int, updates: str) -> str:
    """Update a WHOIS contact. Pass updates as JSON string."""
    try:
        data = json.loads(updates)
        return _ok(client.put(f"/contacts/{id}", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
def openprovider_delete_contact(id: int) -> str:
    """Delete a WHOIS contact. Cannot delete contacts in use by domains."""
    try:
        return _ok(client.delete(f"/contacts/{id}"))
    except OpenproviderError as e:
        return _err(e)


# ============================================================
# Customers
# ============================================================

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_list_customers(
    limit: int = 100,
    offset: int = 0,
    last_name_pattern: str | None = None,
    company_name_pattern: str | None = None,
) -> str:
    """List reseller customers."""
    params: dict = {"limit": limit, "offset": offset}
    if last_name_pattern:
        params["last_name_pattern"] = last_name_pattern
    if company_name_pattern:
        params["company_name_pattern"] = company_name_pattern
    try:
        return _ok(client.get("/customers", params))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_customer(handle: str) -> str:
    """Get customer details by handle."""
    try:
        return _ok(client.get(f"/customers/{handle}"))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
def openprovider_create_customer(customer_data: str) -> str:
    """Create a reseller customer. Pass customer_data as JSON string."""
    try:
        data = json.loads(customer_data)
        return _ok(client.post("/customers", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
def openprovider_update_customer(handle: str, updates: str) -> str:
    """Update a customer. Pass updates as JSON string."""
    try:
        data = json.loads(updates)
        return _ok(client.put(f"/customers/{handle}", data))
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": True})
def openprovider_delete_customer(handle: str) -> str:
    """Delete a customer by handle."""
    try:
        return _ok(client.delete(f"/customers/{handle}"))
    except OpenproviderError as e:
        return _err(e)


# ============================================================
# Invoices (read-only)
# ============================================================

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_list_invoices(
    limit: int = 100,
    offset: int = 0,
) -> str:
    """List invoices from Openprovider (billing history)."""
    try:
        return _ok(client.get("/invoices", {"limit": limit, "offset": offset}))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_invoice(id: int) -> str:
    """Get invoice details by ID."""
    try:
        return _ok(client.get(f"/invoices/{id}"))
    except OpenproviderError as e:
        return _err(e)


# ============================================================
# Payments (read-only)
# ============================================================

@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_list_payments(
    limit: int = 100,
    offset: int = 0,
) -> str:
    """List payments to Openprovider."""
    try:
        return _ok(client.get("/payments", {"limit": limit, "offset": offset}))
    except OpenproviderError as e:
        return _err(e)


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def openprovider_get_payment(id: int) -> str:
    """Get payment details by ID."""
    try:
        return _ok(client.get(f"/payments/{id}"))
    except OpenproviderError as e:
        return _err(e)


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    mcp.run()

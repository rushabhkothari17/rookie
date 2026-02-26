"""Zoho WorkDrive service — folder + file management via WorkDrive REST API v1."""
from __future__ import annotations
import re
import logging
from io import BytesIO
from typing import Any, Dict, Optional

import httpx

from db.session import db
from core.helpers import now_iso

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Datacenter mapping (reuses Zoho Mail pattern)
# ---------------------------------------------------------------------------
DATACENTER_AUTH_URLS: Dict[str, str] = {
    "US": "https://accounts.zoho.com",
    "EU": "https://accounts.zoho.eu",
    "AU": "https://accounts.zoho.com.au",
    "IN": "https://accounts.zoho.in",
    "JP": "https://accounts.zoho.jp",
    "CA": "https://accounts.zohocloud.ca",
}
DATACENTER_API_DOMAINS: Dict[str, str] = {
    "US": "https://www.zohoapis.com",
    "EU": "https://www.zohoapis.eu",
    "AU": "https://www.zohoapis.com.au",
    "IN": "https://www.zohoapis.in",
    "JP": "https://www.zohoapis.jp",
    "CA": "https://www.zohocloud.ca",
}
LOCATION_TO_DC: Dict[str, str] = {
    "us": "US", "eu": "EU", "au": "AU", "in": "IN",
    "jp": "JP", "ca": "CA", "cn": "US",
}

WORKDRIVE_SCOPES = (
    "WorkDrive.files.CREATE,WorkDrive.files.READ,"
    "WorkDrive.files.UPDATE,WorkDrive.files.DELETE,"
    "WorkDrive.teamfolders.READ,WorkDrive.teamfolders.CREATE,"
    "WorkDrive.teamfolders.UPDATE"
)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------------------
# URL / ID helpers
# ---------------------------------------------------------------------------

def extract_folder_id_from_url(url: str) -> Optional[str]:
    """Return the folder/resource ID from a Zoho WorkDrive URL.

    Handles URL patterns such as:
      https://workdrive.zoho.com/teams/TEAM/privatespace/folders/FOLDER_ID
      https://workdrive.zoho.com/folder/FOLDER_ID
      https://workdrive.zoho.com/teams/TEAM/workdrive/folders/FOLDER_ID
    """
    if not url:
        return None
    # Last path segment that looks like a Zoho resource ID
    match = re.search(r"/folders/([A-Za-z0-9_-]+)", url)
    if match:
        return match.group(1)
    # Fallback: last non-empty path segment
    parts = [p for p in url.rstrip("/").split("/") if p]
    if parts:
        return parts[-1]
    return None


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

async def _get_credentials(tenant_id: str) -> Optional[Dict[str, Any]]:
    """Load WorkDrive OAuth credentials from integrations collection."""
    doc = await db.integrations.find_one(
        {"tenant_id": tenant_id, "service": "zoho_workdrive"},
        {"_id": 0},
    )
    return doc


async def _refresh_access_token(tenant_id: str, creds: Dict[str, Any]) -> str:
    """Use the refresh_token to obtain a new access_token. Persists to DB."""
    dc = creds.get("datacenter", "US")
    auth_url = DATACENTER_AUTH_URLS.get(dc, DATACENTER_AUTH_URLS["US"])
    payload = {
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "grant_type": "refresh_token",
        "refresh_token": creds["refresh_token"],
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{auth_url}/oauth/v2/token", data=payload)
        resp.raise_for_status()
        data = resp.json()

    new_access = data.get("access_token")
    if not new_access:
        raise RuntimeError(f"Token refresh failed: {data}")

    await db.integrations.update_one(
        {"tenant_id": tenant_id, "service": "zoho_workdrive"},
        {"$set": {"access_token": new_access, "updated_at": now_iso()}},
    )
    return new_access


async def _get_access_token(tenant_id: str) -> tuple[str, str]:
    """Return (access_token, api_domain) for the tenant, refreshing if needed."""
    creds = await _get_credentials(tenant_id)
    if not creds or not creds.get("is_validated"):
        raise RuntimeError("WorkDrive is not connected for this partner.")

    access_token = creds.get("access_token", "")
    dc = creds.get("datacenter", "US")
    api_domain = DATACENTER_API_DOMAINS.get(dc, DATACENTER_API_DOMAINS["US"])

    # Always attempt a token refresh guard by trying and catching 401 at call site.
    return access_token, api_domain


def _auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Zoho-oauthtoken {token}"}


async def _call(tenant_id: str, method: str, path: str, **kwargs) -> httpx.Response:
    """Make a WorkDrive API call, refreshing the token once on 401."""
    creds = await _get_credentials(tenant_id)
    if not creds:
        raise RuntimeError("WorkDrive not configured")
    dc = creds.get("datacenter", "US")
    api_domain = DATACENTER_API_DOMAINS.get(dc, DATACENTER_API_DOMAINS["US"])
    access_token = creds.get("access_token", "")
    url = f"{api_domain}/workdrive/api/v1{path}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(
            method, url, headers=_auth_headers(access_token), **kwargs
        )
        if resp.status_code == 401:
            access_token = await _refresh_access_token(tenant_id, creds)
            resp = await client.request(
                method, url, headers=_auth_headers(access_token), **kwargs
            )
        return resp


# ---------------------------------------------------------------------------
# Folder operations
# ---------------------------------------------------------------------------

async def create_folder(tenant_id: str, parent_folder_id: str, folder_name: str) -> Dict[str, Any]:
    """Create a sub-folder inside parent_folder_id."""
    resp = await _call(
        tenant_id, "POST",
        f"/files/{parent_folder_id}/folders",
        json={"name": folder_name},
    )
    resp.raise_for_status()
    data = resp.json()
    folder_id = (
        data.get("data", {}).get("id")
        or data.get("data", [{}])[0].get("id", "")
        if isinstance(data.get("data"), list)
        else data.get("data", {}).get("id", "")
    )
    return {"folder_id": folder_id, "folder_name": folder_name}


async def rename_folder(tenant_id: str, folder_id: str, new_name: str) -> None:
    """Rename a folder in WorkDrive."""
    resp = await _call(
        tenant_id, "PUT",
        f"/files/{folder_id}",
        json={"name": new_name},
    )
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

async def upload_file(
    tenant_id: str,
    folder_id: str,
    filename: str,
    content: bytes,
    mime_type: str = "application/octet-stream",
) -> Dict[str, Any]:
    """Upload a file into folder_id. Returns file metadata."""
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"File exceeds 5 MB limit ({len(content) / 1024 / 1024:.1f} MB)")

    files = {"file": (filename, BytesIO(content), mime_type)}
    resp = await _call(tenant_id, "POST", f"/files/{folder_id}/files", files=files)
    resp.raise_for_status()
    data = resp.json()
    # WorkDrive returns data as a list or dict depending on API version
    file_data = data.get("data", {})
    if isinstance(file_data, list):
        file_data = file_data[0] if file_data else {}
    file_id = file_data.get("id", "")
    return {"workdrive_file_id": file_id, "file_name": filename, "file_size": len(content)}


async def list_files(tenant_id: str, folder_id: str) -> list[Dict[str, Any]]:
    """List all files in a WorkDrive folder."""
    resp = await _call(tenant_id, "GET", f"/files/{folder_id}/files")
    resp.raise_for_status()
    data = resp.json()
    raw = data.get("data", [])
    if isinstance(raw, dict):
        raw = raw.get("data", [])
    result = []
    for item in raw:
        attrs = item.get("attributes", item)
        result.append({
            "workdrive_file_id": item.get("id", ""),
            "file_name": attrs.get("name", ""),
            "file_size": attrs.get("size", 0),
            "mime_type": attrs.get("type", ""),
            "modified_at": attrs.get("modified_time", ""),
            "created_at": attrs.get("created_time", ""),
        })
    return result


async def download_file(tenant_id: str, workdrive_file_id: str) -> tuple[bytes, str]:
    """Download file content from WorkDrive. Returns (bytes, filename)."""
    creds = await _get_credentials(tenant_id)
    if not creds:
        raise RuntimeError("WorkDrive not configured")
    dc = creds.get("datacenter", "US")
    api_domain = DATACENTER_API_DOMAINS.get(dc, DATACENTER_API_DOMAINS["US"])
    access_token = creds.get("access_token", "")
    url = f"{api_domain}/workdrive/api/v1/files/{workdrive_file_id}/download"

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        resp = await client.get(url, headers=_auth_headers(access_token))
        if resp.status_code == 401:
            access_token = await _refresh_access_token(tenant_id, creds)
            resp = await client.get(url, headers=_auth_headers(access_token))
        resp.raise_for_status()

    cd = resp.headers.get("content-disposition", "")
    match = re.search(r'filename[^;=\n]*=(["\']?)([^"\'\n;]+)\1', cd)
    filename = match.group(2) if match else workdrive_file_id
    return resp.content, filename


async def delete_file(tenant_id: str, workdrive_file_id: str) -> None:
    """Permanently delete a file from WorkDrive."""
    resp = await _call(tenant_id, "DELETE", f"/files/{workdrive_file_id}")
    if resp.status_code not in (200, 204):
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# OAuth helpers (used by integrations route)
# ---------------------------------------------------------------------------

def build_auth_url(client_id: str, datacenter: str, redirect_uri: str) -> str:
    """Return the Zoho OAuth authorization URL for WorkDrive."""
    base = DATACENTER_AUTH_URLS.get(datacenter.upper(), DATACENTER_AUTH_URLS["US"])
    return (
        f"{base}/oauth/v2/auth"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&scope={WORKDRIVE_SCOPES}"
        f"&redirect_uri={redirect_uri}"
        f"&access_type=offline"
        f"&prompt=consent"
    )


async def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    code: str,
    datacenter: str,
    redirect_uri: str,
) -> Dict[str, Any]:
    """Exchange an OAuth auth code for access_token + refresh_token."""
    auth_url = DATACENTER_AUTH_URLS.get(datacenter.upper(), DATACENTER_AUTH_URLS["US"])
    api_domain = DATACENTER_API_DOMAINS.get(datacenter.upper(), DATACENTER_API_DOMAINS["US"])
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{auth_url}/oauth/v2/token", data=payload)
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        raise RuntimeError(f"Token exchange failed: {data['error']}")

    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "api_domain": api_domain,
    }


async def validate_connection(tenant_id: str) -> bool:
    """Test the WorkDrive connection by listing the root team folders."""
    try:
        resp = await _call(tenant_id, "GET", "/privatespace")
        return resp.status_code in (200, 404)  # 404 = connected but no space = still valid
    except Exception as exc:
        logger.warning("WorkDrive validation failed: %s", exc)
        return False

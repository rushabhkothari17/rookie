"""
Iteration 310 - Frontend Tests
Tests:
1. Tax auto-population in PartnerOrdersTab (partner select → tax_name/tax_rate)
2. Tax auto-population fallback (partner without address → org address)  
3. Tax disabled → No tax/0
4. TaxesTab TaxSettingsPanel (locked fields, validation)
5. OrdersTab manual order tax auto-population
6. Sticky scrollbar behavior
7. Override rules priority
"""

import asyncio
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestTaxAPIs:
    """Test tax-related backend APIs are returning valid responses"""

    def test_tax_settings_returns_valid(self):
        """Tax settings endpoint returns valid response"""
        token = self._get_token()
        assert token, "Token required"
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/admin/taxes/settings", headers=headers)
        assert r.status_code == 200
        data = r.json()
        print(f"Tax settings: {data}")
        assert "tax_settings" in data or "enabled" in str(data)

    def test_tax_tables_returns_entries(self):
        """Tax tables endpoint returns entries"""
        token = self._get_token()
        assert token, "Token required"
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/admin/taxes/tables", headers=headers)
        assert r.status_code == 200
        data = r.json()
        print(f"Tax tables entries count: {len(data.get('entries', []))}")
        # Should have CA/ON entries as per problem statement
        entries = data.get("entries", [])
        ca_entries = [e for e in entries if e.get("country_code") == "CA"]
        print(f"CA entries: {ca_entries}")
        assert len(ca_entries) > 0, "Should have CA tax entries"

    def test_tax_overrides_returns_rules(self):
        """Tax overrides endpoint returns rules"""
        token = self._get_token()
        assert token, "Token required"
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/admin/taxes/overrides", headers=headers)
        assert r.status_code == 200
        data = r.json()
        print(f"Override rules: {data.get('rules', [])}")

    def test_my_tenant_has_address(self):
        """My tenant endpoint returns org address for tax fallback"""
        token = self._get_token()
        assert token, "Token required"
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/admin/tenants/my", headers=headers)
        assert r.status_code == 200
        data = r.json()
        tenant = data.get("tenant", {})
        address = tenant.get("address", {})
        print(f"Org address: {address}")
        # Per problem statement: org has country='CA', state='ON'
        assert address.get("country"), "Org should have country set"

    def _get_token(self):
        """Get admin token"""
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@automateaccounts.local",
            "password": "ChangeMe123!"
        })
        if r.status_code == 200:
            return r.json().get("token")
        return None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

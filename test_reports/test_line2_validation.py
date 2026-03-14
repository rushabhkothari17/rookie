#!/usr/bin/env python3
"""
Script to test line2 validation in signup form by:
1. Setting line2.required=True via admin API
2. Checking the signup API endpoint to verify schema
3. Restoring line2.required=False
"""
import requests
import json

BASE_URL = "https://theme-consistency-8.preview.emergentagent.com"

# Login as admin
login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
    "email": "admin@automateaccounts.local",
    "password": "ChangeMe123!"
})
token = login_resp.json()['token']
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Get current settings
settings_resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=headers)
settings = settings_resp.json().get('settings', {})
schema = settings.get('signup_form_schema', [])

print(f"Current schema has {len(schema)} fields")

# Find address field and check line2
original_line2_required = False
for field in schema:
    if field.get('type') == 'address':
        addr_cfg = field.get('address_config', {})
        line2_cfg = addr_cfg.get('line2', {})
        original_line2_required = line2_cfg.get('required', False)
        print(f"Address field found, line2.required = {original_line2_required}")
        
        # Set line2.required = True
        if 'address_config' not in field:
            field['address_config'] = {}
        if 'line2' not in field['address_config']:
            field['address_config']['line2'] = {}
        field['address_config']['line2']['required'] = True
        break

# Save with line2.required=True
save_resp = requests.put(f"{BASE_URL}/api/admin/website-settings", 
                         json={"signup_form_schema": schema},
                         headers=headers)
print(f"Save with line2 required=True: {save_resp.status_code} - {save_resp.text}")

# Verify
verify_resp = requests.get(f"{BASE_URL}/api/admin/website-settings", headers=headers)
verify_schema = verify_resp.json().get('settings', {}).get('signup_form_schema', [])
for f in verify_schema:
    if f.get('type') == 'address':
        line2_required = f.get('address_config', {}).get('line2', {}).get('required', False)
        print(f"Verified: line2.required = {line2_required}")

print("\nDone - line2 is now set to required=True for E2E test")
print("Run 'python3 /app/test_reports/restore_line2.py' to restore after testing")

# Save restore script
restore_data = json.dumps({"schema": schema, "token": token, "base_url": BASE_URL})
# Restore line2 back
for field in schema:
    if field.get('type') == 'address':
        field['address_config']['line2']['required'] = original_line2_required
        break

restore_resp = requests.put(f"{BASE_URL}/api/admin/website-settings",
                             json={"signup_form_schema": schema},
                             headers=headers)
print(f"\nRestored line2.required={original_line2_required}: {restore_resp.status_code} - {restore_resp.text}")

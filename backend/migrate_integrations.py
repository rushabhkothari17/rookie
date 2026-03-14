"""
One-time migration: copy all data from db.integrations → db.oauth_connections
then drop the db.integrations collection.

Run: python migrate_integrations.py
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


SERVICE_TO_PROVIDER = {
    "zoho_mail": "zoho_mail",
    "zoho_crm": "zoho_crm",
    "zoho_workdrive": "zoho_workdrive",
    "resend_validated": "resend",
    "stripe_validated": "stripe",
    "gocardless_validated": "gocardless",
}


def _dc_lower(val: str) -> str:
    return (val or "us").lower()


async def migrate():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    docs = await db.integrations.find({}, {"_id": 0}).to_list(1000)
    print(f"Found {len(docs)} documents in db.integrations")

    migrated = 0
    skipped = 0

    for doc in docs:
        tid = doc.get("tenant_id")

        # Determine provider
        raw_service = doc.get("service") or doc.get("provider") or ""
        provider = SERVICE_TO_PROVIDER.get(raw_service, raw_service)

        if not tid or not provider:
            print(f"  SKIP (no tenant_id or provider): {doc}")
            skipped += 1
            continue

        # Build the $set payload for oauth_connections
        update: dict = {"tenant_id": tid, "provider": provider}

        # ── Validation-flag documents (resend_validated, stripe_validated, gocardless_validated) ──
        if raw_service in ("resend_validated", "stripe_validated", "gocardless_validated"):
            if doc.get("validated") is not None:
                update["is_validated"] = bool(doc.get("validated"))
            if doc.get("validated_at"):
                update["validated_at"] = doc["validated_at"]
            # Carry over any extra fields to settings
            settings_fields = {k: v for k, v in doc.items()
                               if k not in ("_id", "tenant_id", "service", "provider",
                                            "validated", "validated_at", "error")}
            if settings_fields:
                for k, v in settings_fields.items():
                    update[f"settings.{k}"] = v

            # For gocardless: pick the right provider key based on environment
            if raw_service == "gocardless_validated":
                env = doc.get("environment", "sandbox")
                provider = "gocardless" if env == "live" else "gocardless_sandbox"
                update["provider"] = provider

        # ── Zoho Mail / CRM (credentials stored in integrations) ──
        elif raw_service in ("zoho_mail", "zoho_crm"):
            if doc.get("datacenter"):
                update["data_center"] = _dc_lower(doc["datacenter"])
            # Move validated flag
            if doc.get("validated") is not None:
                update["is_validated"] = bool(doc.get("validated"))
            if doc.get("validated_at"):
                update["validated_at"] = doc["validated_at"]
            # credentials already encrypted — keep as-is
            if doc.get("credentials"):
                update["credentials"] = doc["credentials"]
            # Move non-sensitive Zoho Mail fields to settings
            if raw_service == "zoho_mail":
                for field in ("accounts", "selected_account_id"):
                    if doc.get(field) is not None:
                        update[f"settings.{field}"] = doc[field]

        # ── Zoho WorkDrive ──
        elif raw_service == "zoho_workdrive":
            if doc.get("datacenter"):
                update["data_center"] = _dc_lower(doc["datacenter"])
            update["is_validated"] = bool(doc.get("is_validated", False))
            if doc.get("validated_at"):
                update["validated_at"] = doc["validated_at"]
            if doc.get("connected_at"):
                update["connected_at"] = doc["connected_at"]
            # credentials: access_token and refresh_token may be plain in old docs
            cred_fields = {}
            for f in ("client_id", "client_secret", "access_token", "refresh_token", "api_domain"):
                if doc.get(f):
                    cred_fields[f] = doc[f]
            if cred_fields:
                # If there are already credentials in the doc, merge
                existing_creds = doc.get("credentials", {})
                if isinstance(existing_creds, dict):
                    cred_fields = {**existing_creds, **cred_fields}
                update["credentials"] = cred_fields
            # settings
            for field in ("parent_folder_url", "parent_folder_id"):
                if doc.get(field):
                    update[f"settings.{field}"] = doc[field]

        # ── Zoho Books (uses "provider" key already) ──
        elif raw_service == "zoho_books":
            if doc.get("datacenter"):
                update["data_center"] = _dc_lower(doc["datacenter"])
            update["is_validated"] = bool(doc.get("is_validated", False))
            if doc.get("validated_at"):
                update["validated_at"] = doc["validated_at"]
            # credentials
            cred_fields = {}
            for f in ("client_id", "client_secret", "access_token", "refresh_token"):
                if doc.get(f):
                    cred_fields[f] = doc[f]
            existing_creds = doc.get("credentials", {})
            if isinstance(existing_creds, dict) and existing_creds:
                cred_fields = {**existing_creds, **cred_fields}
            if cred_fields:
                update["credentials"] = cred_fields
            # settings
            for field in ("organization_id", "organization_name"):
                if doc.get(field):
                    update[f"settings.{field}"] = doc[field]

        else:
            print(f"  SKIP unknown service: {raw_service}")
            skipped += 1
            continue

        # Upsert into oauth_connections (don't overwrite if already exists with better data)
        result = await db.oauth_connections.update_one(
            {"tenant_id": tid, "provider": provider},
            {"$setOnInsert": {"tenant_id": tid, "provider": provider},
             "$set": {k: v for k, v in update.items() if k not in ("tenant_id", "provider")}},
            upsert=True
        )
        action = "inserted" if result.upserted_id else "updated"
        print(f"  [{action}] tenant={tid} provider={provider}")
        migrated += 1

    print(f"\nMigration complete: {migrated} migrated, {skipped} skipped")

    # Drop the old collection
    await db.integrations.drop()
    print("db.integrations collection DROPPED")

    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())

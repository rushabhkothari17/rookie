"""
Migration Script: Convert old static product section fields to custom_sections array.

Run ONLY after admin has verified the new UI and given explicit approval.
DO NOT run automatically.

Usage:
  cd /app/backend && python migration_script.py
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid


MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


def make_id() -> str:
    return uuid.uuid4().hex[:16]


def _make_section(name: str, content: str, icon: str, icon_color: str, order: int) -> dict:
    return {
        "id": make_id(),
        "name": name,
        "content": content or "",
        "icon": icon,
        "icon_color": icon_color,
        "tags": [],
        "order": order,
    }


def build_sections_from_product(p: dict) -> list:
    sections = []
    order = 0

    if p.get("outcome"):
        sections.append(_make_section("Outcome", p["outcome"], "Target", "blue", order))
        order += 1

    if p.get("automation_details"):
        sections.append(_make_section("Automation Details", p["automation_details"], "Zap", "purple", order))
        order += 1

    if p.get("support_details"):
        sections.append(_make_section("Support", p["support_details"], "Headphones", "green", order))
        order += 1

    inclusions = p.get("inclusions") or p.get("bullets_included") or []
    if inclusions:
        content = "\n".join(f"- {item}" for item in inclusions)
        sections.append(_make_section("What's Included", content, "CheckCircle", "green", order))
        order += 1

    exclusions = p.get("exclusions") or p.get("bullets_excluded") or []
    if exclusions:
        content = "\n".join(f"- {item}" for item in exclusions)
        sections.append(_make_section("Not Included", content, "XCircle", "red", order))
        order += 1

    requirements = p.get("requirements") or p.get("bullets_needed") or []
    if requirements:
        content = "\n".join(f"- {item}" for item in requirements)
        sections.append(_make_section("What We Need From You", content, "Users", "orange", order))
        order += 1

    next_steps = p.get("next_steps") or []
    if next_steps:
        content = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(next_steps))
        sections.append(_make_section("Next Steps", content, "Rocket", "blue", order))
        order += 1

    return sections


async def run_migration() -> None:
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    products = await db.products.find({}, {"_id": 0}).to_list(10000)
    print(f"Found {len(products)} products to process\n")

    migrated = 0
    skipped = 0

    for p in products:
        if p.get("custom_sections"):
            print(f"  SKIP  {p['id']} | {p['name']!r} — already has {len(p['custom_sections'])} custom section(s)")
            skipped += 1
            continue

        sections = build_sections_from_product(p)
        if not sections:
            sections = [_make_section("Overview", "", "FileText", "blue", 0)]

        await db.products.update_one(
            {"id": p["id"]},
            {"$set": {"custom_sections": sections}},
        )
        print(f"  OK    {p['id']} | {p['name']!r} → {len(sections)} section(s)")
        migrated += 1

    print(f"\n{'=' * 40}")
    print(f"Done!  Migrated: {migrated}  |  Skipped: {skipped}")
    client.close()


if __name__ == "__main__":
    print("=" * 40)
    print("Product Sections Migration Script")
    print("=" * 40)
    print("WARNING: This will add 'custom_sections' to all products that lack it.")
    print("Products that already have 'custom_sections' will be skipped.\n")
    print("Press Enter to proceed or Ctrl+C to abort...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)

    asyncio.run(run_migration())
    print("Migration complete!")

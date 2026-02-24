"""Article Templates routes: CRUD for reusable article templates."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.helpers import make_id, now_iso
from core.tenant import get_tenant_filter, set_tenant_id, tenant_id_of, DEFAULT_TENANT_ID, get_tenant_admin
from core.security import require_admin
from db.session import db

router = APIRouter(prefix="/api", tags=["article-templates"])

DEFAULT_TEMPLATES = [
    {
        "name": "Blog Post",
        "description": "A standard blog post with introduction, body, and conclusion",
        "category": "Blog",
        "is_default": True,
        "content": """<h1>Blog Post Title</h1>
<p>Write a compelling introduction that hooks the reader and summarizes what this post covers.</p>
<h2>Background</h2>
<p>Provide context or background information that the reader needs to understand the topic.</p>
<h2>Main Points</h2>
<p>Discuss your first key point here. Support it with evidence, examples, or data.</p>
<p>Discuss your second key point here.</p>
<h2>Key Takeaways</h2>
<ul>
  <li>Summarize the first key takeaway.</li>
  <li>Summarize the second key takeaway.</li>
  <li>Summarize the third key takeaway.</li>
</ul>
<h2>Conclusion</h2>
<p>Wrap up the post by restating the main points and providing a call to action or next steps.</p>""",
    },
    {
        "name": "Guide / How-To",
        "description": "Step-by-step guide for completing a task or process",
        "category": "Guide",
        "is_default": True,
        "content": """<h1>How to [Task Name]</h1>
<p>A brief overview of what this guide covers and who it is for.</p>
<h2>Prerequisites</h2>
<ul>
  <li>Requirement or resource needed before starting.</li>
  <li>Another prerequisite.</li>
</ul>
<h2>Step 1: [First Step]</h2>
<p>Describe the first step in detail. Include any important notes or warnings.</p>
<h2>Step 2: [Second Step]</h2>
<p>Describe the second step. Add screenshots or examples where helpful.</p>
<h2>Step 3: [Third Step]</h2>
<p>Describe the third step.</p>
<h2>Troubleshooting</h2>
<p>List common issues and their solutions here.</p>
<h2>Summary</h2>
<p>You have now completed [task]. Here is a quick recap of what was covered.</p>""",
    },
    {
        "name": "Standard Operating Procedure (SOP)",
        "description": "Formal SOP document with purpose, scope, and procedures",
        "category": "SOP",
        "is_default": True,
        "content": """<h1>SOP: [Process Name]</h1>
<p><strong>Document ID:</strong> SOP-[NUMBER]</p>
<p><strong>Version:</strong> 1.0</p>
<p><strong>Effective Date:</strong> [DATE]</p>
<p><strong>Owner:</strong> [DEPARTMENT/TEAM]</p>
<h2>1. Purpose</h2>
<p>Describe the purpose of this SOP and the problem it solves.</p>
<h2>2. Scope</h2>
<p>Define who this SOP applies to and under what circumstances it should be followed.</p>
<h2>3. Responsibilities</h2>
<ul>
  <li><strong>[Role 1]:</strong> Responsible for [action].</li>
  <li><strong>[Role 2]:</strong> Responsible for [action].</li>
</ul>
<h2>4. Procedure</h2>
<ol>
  <li>First procedure step. Include details and expected outcomes.</li>
  <li>Second procedure step.</li>
  <li>Third procedure step.</li>
</ol>
<h2>5. Related Documents</h2>
<ul>
  <li>Link to related document or policy.</li>
</ul>
<h2>6. Revision History</h2>
<p>v1.0 — Initial version.</p>""",
    },
    {
        "name": "Scope of Work",
        "description": "Project scope document with deliverables and timeline",
        "category": "Scope - Draft",
        "is_default": True,
        "content": """<h1>Scope of Work — [Project Name]</h1>
<p><strong>Client:</strong> [CLIENT NAME]</p>
<p><strong>Date:</strong> [DATE]</p>
<h2>Project Overview</h2>
<p>Provide a concise description of the project, its objectives, and the problem it solves for the client.</p>
<h2>Deliverables</h2>
<ul>
  <li>Deliverable 1: Description of what will be delivered.</li>
  <li>Deliverable 2: Description.</li>
  <li>Deliverable 3: Description.</li>
</ul>
<h2>Timeline</h2>
<ol>
  <li><strong>Week 1–2:</strong> Discovery and planning phase.</li>
  <li><strong>Week 3–4:</strong> Implementation phase.</li>
  <li><strong>Week 5:</strong> Review and handover.</li>
</ol>
<h2>Assumptions</h2>
<ul>
  <li>List any assumptions made while creating this scope.</li>
</ul>
<h2>Out of Scope</h2>
<ul>
  <li>List items explicitly excluded from this engagement.</li>
</ul>
<h2>Pricing</h2>
<p>Total investment: <strong>$[AMOUNT]</strong></p>""",
    },
]


async def _seed_defaults(tid: str = DEFAULT_TENANT_ID) -> None:
    """Insert default templates for a tenant if none exist."""
    count = await db.article_templates.count_documents({"tenant_id": tid, "is_default": True})
    if count > 0:
        return
    now = now_iso()
    for tpl in DEFAULT_TEMPLATES:
        await db.article_templates.insert_one({
            "id": make_id(),
            "tenant_id": tid,
            "name": tpl["name"],
            "description": tpl["description"],
            "category": tpl["category"],
            "content": tpl["content"],
            "is_default": True,
            "created_at": now,
            "updated_at": now,
        })


@router.get("/article-templates")
async def list_templates(admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    await _seed_defaults(tid)
    templates = await db.article_templates.find(tf, {"_id": 0}).sort("name", 1).to_list(200)
    return {"templates": templates}


@router.post("/article-templates")
async def create_template(payload: Dict[str, Any], admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    tid = tenant_id_of(admin)
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    now = now_iso()
    doc = {
        "id": make_id(),
        "tenant_id": tid,
        "name": name,
        "description": (payload.get("description") or "").strip(),
        "category": (payload.get("category") or "").strip(),
        "content": payload.get("content") or "",
        "is_default": False,
        "created_at": now,
        "updated_at": now,
    }
    await db.article_templates.insert_one(doc)
    return {"template": {k: v for k, v in doc.items() if k != "_id"}}


@router.put("/article-templates/{template_id}")
async def update_template(template_id: str, payload: Dict[str, Any], admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    tpl = await db.article_templates.find_one({**tf, "id": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    update: Dict[str, Any] = {"updated_at": now_iso()}
    for field in ["name", "description", "category", "content"]:
        if field in payload:
            update[field] = payload[field]
    await db.article_templates.update_one({"id": template_id}, {"$set": update})
    updated = await db.article_templates.find_one({"id": template_id}, {"_id": 0})
    return {"template": updated}


@router.delete("/article-templates/{template_id}")
async def delete_template(template_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    tpl = await db.article_templates.find_one({**tf, "id": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.article_templates.delete_one({"id": template_id})
    return {"message": "Deleted"}


@router.get("/article-templates/{template_id}/logs")
async def get_article_template_logs(template_id: str, admin: Dict[str, Any] = Depends(get_tenant_admin)):
    tf = get_tenant_filter(admin)
    tpl = await db.article_templates.find_one({**tf, "id": template_id}, {"_id": 0, "id": 1})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    logs = await db.audit_logs.find(
        {"entity_type": "article_template", "entity_id": template_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"logs": logs}

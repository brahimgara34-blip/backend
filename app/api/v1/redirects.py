import re
from typing import Any, Dict, List
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_redirect_admin_token, get_current_redirect_admin
from app.models.redirect import RedirectRule
from app.schemas.redirect import (
    RedirectLoginRequest,
    RedirectLoginResponse,
    RedirectCreateSchema,
    RedirectUpdateSchema,
    RedirectResponseSchema,
)

router = APIRouter()

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,78}$")
BLOCKED_PREFIXES = ("/ads", "/redirectkiller", "/admin", "/api")


def normalize_slug(raw: str) -> str:
    slug = (raw or "").strip().lower()
    slug = slug.replace(" ", "-")
    slug = re.sub(r"^/+", "", slug)
    slug = re.sub(r"^ads/", "", slug)
    if not SLUG_RE.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="الـ slug يجب أن يحتوي حروفاً إنجليزية صغيرة، أرقاماً وشرطات فقط (مثال: killer)",
        )
    return slug


def normalize_destination(raw: str) -> str:
    dest = (raw or "").strip()
    if dest.startswith("https://vitalismaroc.shop"):
        dest = dest[len("https://vitalismaroc.shop"):] or "/"
    elif dest.startswith("http://vitalismaroc.shop"):
        dest = dest[len("http://vitalismaroc.shop"):] or "/"
    elif dest.startswith("http://") or dest.startswith("https://"):
        parsed = urlparse(dest)
        dest = parsed.path or "/"
    if not dest.startswith("/"):
        dest = "/" + dest
    dest = dest.split("?")[0].split("#")[0]
    dest = re.sub(r"/{2,}", "/", dest)
    if dest != "/" and dest.endswith("/"):
        dest = dest.rstrip("/")
    if any(dest == prefix or dest.startswith(prefix + "/") for prefix in BLOCKED_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لا يمكن توجيه slug نحو /ads أو صفحات الإدارة",
        )
    return dest


@router.post("/login", response_model=RedirectLoginResponse)
async def redirect_admin_login(payload: RedirectLoginRequest):
    if not (settings.REDIRECT_ADMIN_PASSWORD or "").strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="REDIRECT_ADMIN_PASSWORD غير مضبوط في بيئة الخادم",
        )

    req_username = (payload.username or "").strip().lower()
    conf_username = (settings.REDIRECT_ADMIN_USERNAME or "redirectadmin").strip().lower()
    req_password = (payload.password or "").strip()
    conf_password = settings.REDIRECT_ADMIN_PASSWORD.strip()

    if req_username != conf_username or req_password != conf_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="اسم المستخدم أو كلمة المرور غير صحيحة",
        )

    token = create_redirect_admin_token(payload.username.strip())
    return RedirectLoginResponse(
        token=token,
        expires_in_hours=settings.REDIRECT_ADMIN_SESSION_HOURS,
        username=payload.username.strip(),
    )


@router.get("/resolve/{slug}")
async def resolve_redirect(slug: str, db: AsyncSession = Depends(get_db)):
    clean_slug = normalize_slug(slug)
    result = await db.execute(select(RedirectRule).where(RedirectRule.slug == clean_slug))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="slug غير موجود")
    return {"slug": rule.slug, "destination": rule.destination}


@router.get("/", response_model=List[RedirectResponseSchema])
async def list_redirects(
    admin: Dict[str, Any] = Depends(get_current_redirect_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(RedirectRule).order_by(RedirectRule.updated_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=RedirectResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_redirect(
    payload: RedirectCreateSchema,
    admin: Dict[str, Any] = Depends(get_current_redirect_admin),
    db: AsyncSession = Depends(get_db),
):
    slug = normalize_slug(payload.slug)
    destination = normalize_destination(payload.destination)

    existing = await db.execute(select(RedirectRule).where(RedirectRule.slug == slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="هذا الـ slug مستعمل من قبل")

    rule = RedirectRule(
        slug=slug,
        destination=destination,
        label=(payload.label or "").strip() or None,
        note=(payload.note or "").strip() or None,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=RedirectResponseSchema)
async def update_redirect(
    rule_id: int,
    payload: RedirectUpdateSchema,
    admin: Dict[str, Any] = Depends(get_current_redirect_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(RedirectRule).where(RedirectRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="القاعدة غير موجودة")

    if payload.slug is not None:
        new_slug = normalize_slug(payload.slug)
        clash = await db.execute(
            select(RedirectRule).where(RedirectRule.slug == new_slug, RedirectRule.id != rule_id)
        )
        if clash.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="هذا الـ slug مستعمل من قبل")
        rule.slug = new_slug
    if payload.destination is not None:
        rule.destination = normalize_destination(payload.destination)
    if payload.label is not None:
        rule.label = payload.label.strip() or None
    if payload.note is not None:
        rule.note = payload.note.strip() or None

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_redirect(
    rule_id: int,
    admin: Dict[str, Any] = Depends(get_current_redirect_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(RedirectRule).where(RedirectRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="القاعدة غير موجودة")
    await db.delete(rule)
    await db.commit()
    return None

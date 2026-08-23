import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_, delete
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_admin_token, get_current_admin
from app.models.order import Order, OrderItem, TrackingEvent
from app.models.analytics import ClickEvent
from app.schemas.admin import AdminLoginRequest, AdminLoginResponse, OrderStatusUpdate

router = APIRouter()


def _get_date_bounds(range_key: str, start_str: Optional[str] = None, end_str: Optional[str] = None):
    """
    Computes start and end datetime based on selected range key.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    today_start = datetime.datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=datetime.timezone.utc)

    if range_key == "today":
        return today_start, now
    elif range_key == "yesterday":
        yesterday_start = today_start - datetime.timedelta(days=1)
        yesterday_end = today_start - datetime.timedelta(seconds=1)
        return yesterday_start, yesterday_end
    elif range_key == "7d":
        return today_start - datetime.timedelta(days=6), now
    elif range_key == "30d":
        return today_start - datetime.timedelta(days=29), now
    elif range_key == "custom" and start_str:
        try:
            s_dt = datetime.datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
            if end_str:
                e_dt = datetime.datetime.strptime(end_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=datetime.timezone.utc)
            else:
                e_dt = now
            return s_dt, e_dt
        except Exception:
            return None, None
    # "all" or default -> no date filter
    return None, None


# ── 1. Admin Authentication ──────────────────────────────────────────────────
@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(payload: AdminLoginRequest):
    if payload.username.strip() != settings.ADMIN_USERNAME or payload.password != settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="اسم المستخدم أو كلمة المرور غير صحيحة"
        )
    
    token = create_admin_token(payload.username)
    return AdminLoginResponse(
        token=token,
        token_type="Bearer",
        expires_in_hours=settings.ADMIN_SESSION_HOURS,
        username=payload.username
    )


# ── 2. Admin Metrics & Stats ─────────────────────────────────────────────────
@router.get("/stats")
async def get_admin_stats(
    range: str = Query("all", description="today, yesterday, 7d, 30d, all, custom"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: Dict[str, Any] = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    start_dt, end_dt = _get_date_bounds(range, start_date, end_date)

    # Base filters
    order_filter = []
    click_filter = []
    if start_dt:
        order_filter.append(Order.created_at >= start_dt)
        click_filter.append(ClickEvent.created_at >= start_dt)
    if end_dt:
        order_filter.append(Order.created_at <= end_dt)
        click_filter.append(ClickEvent.created_at <= end_dt)

    # 1. Fetch Orders
    stmt_orders = select(Order)
    if order_filter:
        stmt_orders = stmt_orders.where(and_(*order_filter))
    res_orders = await db.execute(stmt_orders.order_by(Order.created_at.desc()))
    all_orders: List[Order] = list(res_orders.scalars().all())

    total_orders = len(all_orders)
    total_revenue = sum(float(o.total_amount or 0.0) for o in all_orders if "ملغي" not in str(o.status))
    aov = (total_revenue / total_orders) if total_orders > 0 else 0.0

    # Orders status breakdown
    status_counts: Dict[str, int] = {
        "طلب جديد مؤكد (COD)": 0,
        "تم التأكيد هاتفياً": 0,
        "قيد الشحن والتوصيل": 0,
        "تم التسليم بنجاح": 0,
        "ملغي من الزبون": 0,
        "مرتجع": 0,
    }
    for o in all_orders:
        st = o.status or "طلب جديد مؤكد (COD)"
        status_counts[st] = status_counts.get(st, 0) + 1

    # Upsell metrics
    upsell_orders = [o for o in all_orders if o.has_upsell]
    upsell_orders_count = len(upsell_orders)
    upsell_revenue = sum(float(o.upsell_amount or 199.0) for o in upsell_orders)
    upsell_take_rate = (upsell_orders_count / total_orders * 100) if total_orders > 0 else 0.0

    # 2. Fetch Clicks (Filtered by Valid Morocco IPs)
    stmt_clicks = select(
        func.count(ClickEvent.id).label("total_clicks"),
        func.count(ClickEvent.id).filter(ClickEvent.is_valid_morocco == True).label("valid_ma_clicks"),
        func.count(ClickEvent.id).filter(ClickEvent.is_valid_morocco == False).label("blocked_vpn_clicks"),
    )
    if click_filter:
        stmt_clicks = stmt_clicks.where(and_(*click_filter))
    res_clicks = await db.execute(stmt_clicks)
    clicks_row = res_clicks.one_or_none()
    
    total_clicks = clicks_row.total_clicks if clicks_row else 0
    valid_ma_clicks = clicks_row.valid_ma_clicks if clicks_row else 0
    blocked_vpn_clicks = clicks_row.blocked_vpn_clicks if clicks_row else 0

    # Accurate Conversion Rate: Orders divided by Clean Moroccan Visitors (Non-VPN)
    # If clicks is 0, fallback to orders count to avoid div by zero
    cvr = (total_orders / valid_ma_clicks * 100) if valid_ma_clicks > 0 else (100.0 if total_orders > 0 else 0.0)

    # 3. Product & Tier Breakdown
    product_stats: Dict[str, Dict[str, Any]] = {
        "HydroPure™": {"name": "دوش التوربو المفلتر HydroPure™", "sku": "VM-SHW-01", "units": 0, "revenue": 0.0},
        "AuraFloss™": {"name": "خيط الأسنان المائي AuraFloss™", "sku": "VM-FLS-02", "units": 0, "revenue": 0.0},
        "ErgoCushion™": {"name": "وسادة المقعد التقويمية ErgoCushion™", "sku": "VM-CSH-03", "units": 0, "revenue": 0.0},
    }
    tier_counts = {"1_piece": 0, "2_pieces": 0, "3_pieces": 0}

    for o in all_orders:
        # Items
        items_list = o.items or []
        for itm in items_list:
            name = str(itm.get("name", "")).lower()
            qty = int(itm.get("quantity", 1))
            price = float(itm.get("price", 249.0)) * qty

            if "shower" in name or "hydropure" in name or "دوش" in name or "رشاش" in name:
                product_stats["HydroPure™"]["units"] += qty
                product_stats["HydroPure™"]["revenue"] += price
            elif "flosser" in name or "aurafloss" in name or "خيط" in name or "الأسنان" in name:
                product_stats["AuraFloss™"]["units"] += qty
                product_stats["AuraFloss™"]["revenue"] += price
            elif "cushion" in name or "ergocushion" in name or "وسادة" in name or "مقعد" in name:
                product_stats["ErgoCushion™"]["units"] += qty
                product_stats["ErgoCushion™"]["revenue"] += price
            
            # Tier count estimation
            if qty == 1:
                tier_counts["1_piece"] += 1
            elif qty == 2:
                tier_counts["2_pieces"] += 1
            elif qty >= 3:
                tier_counts["3_pieces"] += 1

    # 4. Top Moroccan Cities Breakdown
    city_stats: Dict[str, Dict[str, Any]] = {}
    for o in all_orders:
        c = o.city or "غير محدد"
        if c not in city_stats:
            city_stats[c] = {"city": c, "orders": 0, "revenue": 0.0}
        city_stats[c]["orders"] += 1
        city_stats[c]["revenue"] += float(o.total_amount or 0.0)

    sorted_cities = sorted(city_stats.values(), key=lambda x: x["orders"], reverse=True)[:8]

    # 5. Timeline Chart Data (Grouped by Date)
    timeline_map: Dict[str, Dict[str, Any]] = {}
    for o in all_orders:
        if o.created_at:
            d_str = o.created_at.strftime("%Y-%m-%d")
            if d_str not in timeline_map:
                timeline_map[d_str] = {"date": d_str, "orders": 0, "revenue": 0.0, "clicks": 0}
            timeline_map[d_str]["orders"] += 1
            timeline_map[d_str]["revenue"] += float(o.total_amount or 0.0)

    # Aggregate clicks by date into timeline
    stmt_click_days = select(
        func.to_char(ClickEvent.created_at, 'YYYY-MM-DD').label("day"),
        func.count(ClickEvent.id).label("day_clicks")
    )
    if click_filter:
        stmt_click_days = stmt_click_days.where(and_(*click_filter))
    stmt_click_days = stmt_click_days.group_by("day")
    res_click_days = await db.execute(stmt_click_days)
    for row in res_click_days.all():
        d_str = str(row.day)
        if d_str not in timeline_map:
            timeline_map[d_str] = {"date": d_str, "orders": 0, "revenue": 0.0, "clicks": 0}
        timeline_map[d_str]["clicks"] += row.day_clicks

    sorted_timeline = sorted(timeline_map.values(), key=lambda x: x["date"])

    return {
        "kpis": {
            "total_revenue": round(total_revenue, 2),
            "total_orders": total_orders,
            "confirmed_orders": status_counts.get("تم التأكيد هاتفياً", 0) + status_counts.get("قيد الشحن والتوصيل", 0) + status_counts.get("تم التسليم بنجاح", 0),
            "aov": round(aov, 2),
            "valid_morocco_clicks": valid_ma_clicks,
            "blocked_vpn_clicks": blocked_vpn_clicks,
            "total_clicks": total_clicks,
            "cvr_percent": round(cvr, 2),
            "upsell_orders_count": upsell_orders_count,
            "upsell_revenue": round(upsell_revenue, 2),
            "upsell_take_rate": round(upsell_take_rate, 2),
        },
        "status_breakdown": status_counts,
        "product_breakdown": list(product_stats.values()),
        "tier_breakdown": tier_counts,
        "cities_breakdown": sorted_cities,
        "timeline": sorted_timeline,
        "range": range,
    }


# ── 3. Orders Management (List & Search) ──────────────────────────────────────
@router.get("/orders")
async def get_admin_orders(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    range: str = Query("all"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    admin: Dict[str, Any] = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    start_dt, end_dt = _get_date_bounds(range, start_date, end_date)
    conditions = []

    if start_dt:
        conditions.append(Order.created_at >= start_dt)
    if end_dt:
        conditions.append(Order.created_at <= end_dt)
    if status and status != "all":
        conditions.append(Order.status == status)
    if search:
        s = f"%{search.strip()}%"
        conditions.append(or_(
            Order.order_id.ilike(s),
            Order.customer_name.ilike(s),
            Order.phone_number.ilike(s),
            Order.city.ilike(s)
        ))

    # Total count query
    count_stmt = select(func.count(Order.id))
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total_count = (await db.execute(count_stmt)).scalar() or 0

    # Paginated orders
    stmt = select(Order)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(Order.created_at.desc()).offset((page - 1) * limit).limit(limit)
    res = await db.execute(stmt)
    orders = res.scalars().all()

    # Format orders for JSON response
    items_out = []
    for o in orders:
        items_out.append({
            "id": o.id,
            "orderId": o.order_id,
            "customerName": o.customer_name,
            "phoneNumber": o.phone_number,
            "normalizedPhone": o.normalized_phone,
            "totalAmount": float(o.total_amount),
            "hasUpsell": o.has_upsell,
            "upsellProduct": o.upsell_product,
            "upsellAmount": float(o.upsell_amount or 0.0),
            "status": o.status or "طلب جديد مؤكد (COD)",
            "city": o.city or "المغرب",
            "region": o.region or "",
            "country": o.country or "MA",
            "isProxy": o.is_proxy or False,
            "riskScore": float(o.risk_score or 0.0),
            "clientIp": o.client_ip or "",
            "items": o.items or [],
            "createdAt": o.created_at.isoformat() if o.created_at else "",
        })

    return {
        "orders": items_out,
        "total": total_count,
        "page": page,
        "limit": limit,
        "pages": (total_count + limit - 1) // limit if limit > 0 else 1
    }


# ── 4. Update Order Status ────────────────────────────────────────────────────
@router.patch("/orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    admin: Dict[str, Any] = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Order).where(Order.order_id == order_id)
    res = await db.execute(stmt)
    order = res.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    order.status = payload.status
    await db.commit()
    await db.refresh(order)

    return {
        "status": "success",
        "message": f"تم تحديث حالة الطلب #{order_id} بنجاح إلى '{payload.status}'",
        "orderId": order.order_id,
        "newStatus": order.status
    }


# ── 5. Delete Order ───────────────────────────────────────────────────────────
@router.delete("/orders/{order_id}")
async def delete_order(
    order_id: str,
    admin: Dict[str, Any] = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Order).where(Order.order_id == order_id)
    res = await db.execute(stmt)
    order = res.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    await db.delete(order)
    await db.commit()

    return {"status": "success", "message": f"تم حذف الطلب #{order_id} بنجاح"}


# ── 6. Visitor Clicks & Traffic Quality Log ──────────────────────────────────
@router.get("/clicks")
async def get_recent_clicks(
    limit: int = Query(50, ge=1, le=200),
    admin: Dict[str, Any] = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ClickEvent).order_by(ClickEvent.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    clicks = res.scalars().all()

    return [
        {
            "id": c.id,
            "path": c.path,
            "clientIp": c.client_ip,
            "country": c.country,
            "city": c.city,
            "region": c.region,
            "isProxy": c.is_proxy,
            "riskScore": float(c.risk_score or 0.0),
            "isValidMorocco": c.is_valid_morocco,
            "referrer": c.referrer,
            "createdAt": c.created_at.isoformat() if c.created_at else "",
        }
        for c in clicks
    ]

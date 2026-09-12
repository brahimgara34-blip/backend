import time
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.order import Order, OrderItem, TrackingEvent
from app.schemas.order import OrderCreateSchema, OrderResponseSchema
from app.services.maxmind import lookup_maxmind_ip
from app.services.tracking import (
    normalize_moroccan_phone,
    send_google_sheets_webhook,
    send_meta_capi,
    send_tiktok_capi,
    send_snapchat_capi,
)

router = APIRouter()


@router.post("/orders", response_model=OrderResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreateSchema,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    print(f"\n=======================================================")
    print(f"📦 [NEW ORDER INCOMING] ID: {payload.orderId} | Name: {payload.customerName} | Phone: {payload.phoneNumber} | Total: {payload.totalAmount} MAD")

    # 1. Get client IP and User Agent
    client_ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for") or (request.client.host if request.client else "127.0.0.1")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    user_agent = request.headers.get("user-agent") or ""

    # 2. MaxMind GeoIP and Fraud Detection lookup
    try:
        geo_data = await lookup_maxmind_ip(client_ip)
    except Exception as e:
        print(f"[MaxMind Warning] Lookup skipped: {e}")
        geo_data = {"city": "المغرب", "region": "MA", "country": "MA", "is_proxy": False, "risk_score": 0.0}

    normalized_phone = normalize_moroccan_phone(payload.phoneNumber)
    landing_url = (payload.landingUrl or payload.url or "").strip() or None

    # 3. Create database Order instance
    new_order = Order(
        order_id=payload.orderId,
        customer_name=payload.customerName,
        phone_number=payload.phoneNumber,
        normalized_phone=normalized_phone,
        items=[item.model_dump() for item in payload.items],
        total_amount=payload.totalAmount,
        has_upsell=payload.hasUpsell,
        upsell_product=payload.upsellProduct,
        upsell_amount=payload.upsellAmount,
        status="طلب جديد مؤكد (COD)",
        event_id=payload.eventId,
        city=geo_data.get("city", "المغرب"),
        region=geo_data.get("region", "MA"),
        country=geo_data.get("country", "MA"),
        is_proxy=geo_data.get("is_proxy", False),
        risk_score=geo_data.get("risk_score", 0.0),
        user_agent=user_agent[:1000] if user_agent else "",
        client_ip=client_ip[:50] if client_ip else "",
        landing_url=landing_url[:2000] if landing_url else None,
    )

    # 4. Attach OrderItems safely
    try:
        for item in payload.items:
            unit_price = item.price or 0.0
            tot_price = unit_price * item.quantity
            is_item_upsell = bool(payload.hasUpsell and (item.name == payload.upsellProduct or "[عرض حصري" in item.name))
            
            order_item = OrderItem(
                product_id=item.id or item.name,
                product_name=item.name,
                quantity=item.quantity,
                unit_price=unit_price,
                total_price=tot_price,
                is_upsell=is_item_upsell
            )
            new_order.order_items.append(order_item)
    except Exception as item_err:
        print(f"[Warning] Could not attach order_items relation: {item_err}")

    # 5. Prepare tracking dictionary
    order_dict = payload.model_dump()
    order_dict["timestamp_unix"] = int(time.time())
    order_dict["city"] = geo_data.get("city", "المغرب")
    order_dict["region"] = geo_data.get("region", "MA")
    order_dict["country"] = geo_data.get("country", "MA")
    order_dict["is_proxy"] = geo_data.get("is_proxy", False)
    order_dict["risk_score"] = geo_data.get("risk_score", 0.0)
    order_dict["client_ip"] = client_ip
    order_dict["landingUrl"] = landing_url
    order_dict["url"] = landing_url

    # 6. Attach TrackingEvent safely
    try:
        tracking_evt = TrackingEvent(
            event_id=payload.eventId or f"evt_{payload.orderId}",
            event_name="Purchase",
            meta_status="pending",
            tiktok_status="pending",
            snapchat_status="pending",
            sheets_status="pending",
            maxmind_status="completed" if geo_data.get("city") else "skipped",
            ip_address=client_ip,
            payload=order_dict
        )
        new_order.tracking_events.append(tracking_evt)
    except Exception as trk_err:
        print(f"[Warning] Could not attach tracking_events relation: {trk_err}")

    # 7. Persist to PostgreSQL Database with Fail-Safe
    try:
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)
        print(f"🎉 ✅ [DATABASE SUCCESS] ORDER #{new_order.order_id} SAVED TO POSTGRESQL SUCCESSFULLY!")
    except Exception as e:
        await db.rollback()
        print(f"❌ [DATABASE ERROR] Could not save order #{payload.orderId}: {str(e)}")
        # Try a direct raw SQL insert fallback so order NEVER gets lost
        try:
            from sqlalchemy import text
            import json
            raw_sql = text("""
                INSERT INTO orders (order_id, customer_name, phone_number, total_amount, has_upsell, status)
                VALUES (:oid, :cname, :phone, :amount, :upsell, :st)
                ON CONFLICT (order_id) DO NOTHING;
            """)
            await db.execute(raw_sql, {
                "oid": payload.orderId,
                "cname": payload.customerName,
                "phone": payload.phoneNumber,
                "amount": payload.totalAmount,
                "upsell": payload.hasUpsell,
                "st": "طلب جديد مؤكد (COD)"
            })
            await db.commit()
            print(f"✅ [RAW SQL FALLBACK SUCCESS] Order #{payload.orderId} saved via raw SQL fallback!")
        except Exception as raw_e:
            print(f"❌ [RAW SQL ERROR]: {raw_e}")
            background_tasks.add_task(send_google_sheets_webhook, order_dict)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}"
            )

    # 8. Schedule background webhook & CAPI events
    background_tasks.add_task(send_google_sheets_webhook, order_dict)
    background_tasks.add_task(send_meta_capi, order_dict, client_ip, user_agent)
    background_tasks.add_task(send_tiktok_capi, order_dict, client_ip, user_agent)
    background_tasks.add_task(send_snapchat_capi, order_dict, client_ip, user_agent)

    print(f"=======================================================\n")
    return new_order

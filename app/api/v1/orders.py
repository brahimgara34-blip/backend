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
    print(f"\n🔔 [New Order Received] ID: {payload.orderId} | Customer: {payload.customerName} | Phone: {payload.phoneNumber} | Total: {payload.totalAmount} MAD")

    # 1. Get client IP and User Agent
    client_ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for") or (request.client.host if request.client else "127.0.0.1")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    user_agent = request.headers.get("user-agent") or ""

    # 2. MaxMind GeoIP and Fraud Detection lookup
    geo_data = await lookup_maxmind_ip(client_ip)
    normalized_phone = normalize_moroccan_phone(payload.phoneNumber)

    # 3. Create database Order instance
    new_order = Order(
        order_id=payload.orderId,
        customer_name=payload.customerName,
        phone_number=payload.phoneNumber,
        normalized_phone=normalized_phone,
        total_amount=payload.totalAmount,
        has_upsell=payload.hasUpsell,
        upsell_product=payload.upsellProduct,
        upsell_amount=payload.upsellAmount,
        status="طلب جديد مؤكد (COD)",
        event_id=payload.eventId,
        city=geo_data.get("city"),
        region=geo_data.get("region"),
        country=geo_data.get("country", "MA"),
        is_proxy=geo_data.get("is_proxy", False),
        risk_score=geo_data.get("risk_score", 0.0),
        user_agent=user_agent,
        client_ip=client_ip
    )

    # 4. Attach OrderItems (order_items table)
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
        new_order.items.append(order_item)

    # 5. Prepare tracking dictionary
    order_dict = payload.model_dump()
    order_dict["timestamp_unix"] = int(time.time())
    order_dict["city"] = geo_data.get("city")
    order_dict["region"] = geo_data.get("region")
    order_dict["country"] = geo_data.get("country", "MA")
    order_dict["is_proxy"] = geo_data.get("is_proxy", False)
    order_dict["risk_score"] = geo_data.get("risk_score", 0.0)
    order_dict["client_ip"] = client_ip

    # 6. Attach TrackingEvent (tracking_events table)
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

    # 7. Persist to PostgreSQL Database
    try:
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)
        print(f"✅ [Database Success] Order #{new_order.order_id} saved successfully with {len(new_order.items)} items!")
    except Exception as e:
        await db.rollback()
        print(f"❌ [Database Error] Failed to insert order #{payload.orderId} into PostgreSQL: {str(e)}")
        # Raise HTTP exception with clean message
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while creating order: {str(e)}"
        )

    # 8. Schedule background webhook & CAPI events
    background_tasks.add_task(send_google_sheets_webhook, order_dict)
    background_tasks.add_task(send_meta_capi, order_dict, client_ip, user_agent)
    background_tasks.add_task(send_tiktok_capi, order_dict, client_ip, user_agent)
    background_tasks.add_task(send_snapchat_capi, order_dict, client_ip, user_agent)

    return new_order

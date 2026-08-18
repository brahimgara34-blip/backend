import time
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.order import Order
from app.schemas.order import OrderCreateSchema, OrderResponseSchema
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
    # Get client info
    client_ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "127.0.0.1")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    user_agent = request.headers.get("user-agent") or ""

    normalized_phone = normalize_moroccan_phone(payload.phoneNumber)

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
        user_agent=user_agent,
        client_ip=client_ip
    )

    try:
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while creating order: {str(e)}"
        )

    # Prepare tracking dictionary
    order_dict = payload.model_dump()
    order_dict["timestamp_unix"] = int(time.time())

    # Schedule background webhook & CAPI events (Meta, TikTok, Snapchat)
    background_tasks.add_task(send_google_sheets_webhook, order_dict)
    background_tasks.add_task(send_meta_capi, order_dict, client_ip, user_agent)
    background_tasks.add_task(send_tiktok_capi, order_dict, client_ip, user_agent)
    background_tasks.add_task(send_snapchat_capi, order_dict, client_ip, user_agent)

    return new_order

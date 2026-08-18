import hashlib
import re
from typing import Dict, Any
import httpx
from app.core.config import settings


def sha256_hash(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def normalize_moroccan_phone(phone: str) -> str:
    cleaned = "".join(filter(str.isdigit, phone))
    if cleaned.startswith("0"):
        cleaned = "212" + cleaned[1:]
    elif not cleaned.startswith("212"):
        cleaned = "212" + cleaned
    return "+" + cleaned


async def send_google_sheets_webhook(order_data: Dict[str, Any]):
    if not settings.GOOGLE_SHEET_WEBHOOK_URL:
        return
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                settings.GOOGLE_SHEET_WEBHOOK_URL,
                json=order_data,
                timeout=10.0
            )
        except Exception as e:
            print(f"[Webhook Error] Failed to send to Google Sheets: {e}")


async def send_meta_capi(order_data: Dict[str, Any], client_ip: str, user_agent: str):
    if not settings.META_CAPI_TOKEN or not settings.META_PIXEL_ID:
        return

    url = f"https://graph.facebook.com/v19.0/{settings.META_PIXEL_ID}/events?access_token={settings.META_CAPI_TOKEN}"
    norm_phone = normalize_moroccan_phone(order_data["phoneNumber"])

    payload = {
        "data": [{
            "event_name": "Purchase",
            "event_time": int(order_data.get("timestamp_unix", 1720000000)),
            "event_id": order_data.get("eventId"),
            "action_source": "website",
            "user_data": {
                "ph": [sha256_hash(norm_phone)],
                "fn": [sha256_hash(order_data["customerName"])],
                "client_ip_address": client_ip,
                "client_user_agent": user_agent,
                "country": [sha256_hash("ma")]
            },
            "custom_data": {
                "currency": "MAD",
                "value": float(order_data["totalAmount"]),
                "content_type": "product",
                "contents": [
                    {"id": item.get("id") or item.get("name"), "quantity": item.get("quantity", 1)}
                    for item in order_data.get("items", [])
                ]
            }
        }]
    }

    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=payload, timeout=6.0)
        except Exception as e:
            print(f"[Meta CAPI Error]: {e}")


async def send_tiktok_capi(order_data: Dict[str, Any], client_ip: str, user_agent: str):
    if not settings.TIKTOK_ACCESS_TOKEN or not settings.TIKTOK_PIXEL_ID:
        return

    url = "https://business-api.tiktok.com/open_api/v1.3/event/track/"
    norm_phone = normalize_moroccan_phone(order_data["phoneNumber"])

    payload = {
        "event_source": "web",
        "event_source_id": settings.TIKTOK_PIXEL_ID,
        "data": [{
            "event": "CompletePayment",
            "event_time": int(order_data.get("timestamp_unix", 1720000000)),
            "event_id": order_data.get("eventId"),
            "user": {
                "phone": sha256_hash(norm_phone),
                "ip": client_ip,
                "user_agent": user_agent
            },
            "properties": {
                "currency": "MAD",
                "value": float(order_data["totalAmount"]),
                "contents": [
                    {"content_id": item.get("id") or item.get("name"), "quantity": item.get("quantity", 1)}
                    for item in order_data.get("items", [])
                ]
            }
        }]
    }

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                url,
                json=payload,
                headers={"Access-Token": settings.TIKTOK_ACCESS_TOKEN},
                timeout=6.0
            )
        except Exception as e:
            print(f"[TikTok CAPI Error]: {e}")


async def send_snapchat_capi(order_data: Dict[str, Any], client_ip: str, user_agent: str):
    if not settings.SNAPCHAT_API_TOKEN or not settings.SNAPCHAT_PIXEL_ID:
        return

    url = f"https://tr.snapchat.com/v2/conversion"
    norm_phone = normalize_moroccan_phone(order_data["phoneNumber"])

    payload = {
        "pixel_id": settings.SNAPCHAT_PIXEL_ID,
        "event": "PURCHASE",
        "event_time": int(order_data.get("timestamp_unix", 1720000000)),
        "event_conversion_type": "WEB",
        "event_tag": order_data.get("eventId"),
        "user_data": {
            "phone_number": sha256_hash(norm_phone),
            "client_ip_address": client_ip,
            "client_user_agent": user_agent,
        },
        "custom_data": {
            "currency": "MAD",
            "price": str(float(order_data["totalAmount"])),
            "item_ids": [
                item.get("id") or item.get("name")
                for item in order_data.get("items", [])
            ],
            "number_items": str(sum(item.get("quantity", 1) for item in order_data.get("items", []))),
        },
    }

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.SNAPCHAT_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                timeout=6.0
            )
        except Exception as e:
            print(f"[Snapchat CAPI Error]: {e}")

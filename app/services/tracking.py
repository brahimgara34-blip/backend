import hashlib
import re
from datetime import datetime
from typing import Dict, Any, List
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


def format_moroccan_phone_for_sheets(phone: str) -> str:
    """Formats phone number as '212 681825745' for Google Sheets."""
    cleaned = "".join(filter(str.isdigit, phone))
    if cleaned.startswith("0"):
        cleaned = cleaned[1:]
    elif cleaned.startswith("212"):
        cleaned = cleaned[3:]
    return f"212 {cleaned}"


def get_item_sku(item_id: str, item_name: str) -> str:
    """Maps product ID or name to its official store SKU."""
    item_id_lower = str(item_id or "").lower()
    item_name_lower = str(item_name or "").lower()
    
    if "shower" in item_id_lower or "hydropure" in item_name_lower or "دوش" in item_name_lower or "رشاش" in item_name_lower:
        return "VM-SHW-01"
    if "flosser" in item_id_lower or "aurafloss" in item_name_lower or "خيط" in item_name_lower or "الأسنان" in item_name_lower:
        return "VM-FLS-02"
    if "cushion" in item_id_lower or "ergocushion" in item_name_lower or "وسادة" in item_name_lower or "مقعد" in item_name_lower:
        return "VM-CSH-03"
    
    clean_id = re.sub(r"[^A-Za-z0-9]", "", item_id.upper()) if item_id else "PROD"
    return f"VM-{clean_id[:6]}-01"


async def send_google_sheets_webhook(order_data: Dict[str, Any]):
    if not settings.GOOGLE_SHEET_WEBHOOK_URL:
        return
    
    # 1. Date format (DD/MM/YYYY)
    now = datetime.now()
    date_formatted = now.strftime("%d/%m/%Y")
    
    # 2. Order ID (starts with vitalis)
    raw_order_id = str(order_data.get("orderId") or order_data.get("order_id") or "")
    if not raw_order_id.lower().startswith("vitalis"):
        clean_num = re.sub(r"^VM-?", "", raw_order_id, flags=re.IGNORECASE) or str(int(now.timestamp()))
        order_id_formatted = f"vitalis-{clean_num}"
    else:
        order_id_formatted = raw_order_id

    # 3. Country (always maroc)
    country_formatted = "maroc"

    # 4. Customer Name
    customer_name = order_data.get("customerName") or order_data.get("customer_name") or "عميل فيتاليس ماروك"

    # 5. Customer Phone (212 681825745)
    raw_phone = str(order_data.get("phoneNumber") or order_data.get("phone_number") or "")
    phone_formatted = format_moroccan_phone_for_sheets(raw_phone)

    # 6. Items processing: product, sku, quantity formatted with '/' separator
    items_list: List[Dict[str, Any]] = order_data.get("items") or []
    products: List[str] = []
    skus: List[str] = []
    quantities: List[str] = []

    for item in items_list:
        name = item.get("name", "منتج فيتاليس ماروك")
        # Clean upsell prefix if present
        clean_name = re.sub(r"^\[.*?\]\s*", "", name)
        products.append(clean_name)
        
        sku = item.get("sku") or get_item_sku(item.get("id", ""), clean_name)
        skus.append(sku)
        
        qty = str(item.get("quantity", 1))
        quantities.append(qty)

    product_str = "/".join(products) if products else "منتج فيتاليس ماروك"
    sku_str = "/".join(skus) if skus else "VM-SHW-01"
    quantity_str = "/".join(quantities) if quantities else "1"

    # 7. Total Price & Currency
    total_price = float(order_data.get("totalAmount") or order_data.get("total_amount") or 0.0)
    currency_str = "SAR (الدرهم.المغربي)"

    # Payload matching the exact Google Sheet / Excel schema
    sheets_payload = {
        # Exact column keys
        "date": date_formatted,
        "orderid": order_id_formatted,
        "country": country_formatted,
        "name": customer_name,
        "phone": phone_formatted,
        "product": product_str,
        "sku": sku_str,
        "quantity": quantity_str,
        "total price": total_price,
        "total_price": total_price,
        "currency": currency_str,
        "status": "",
        
        # Backward-compatible keys
        "orderId": order_id_formatted,
        "customerName": customer_name,
        "phoneNumber": phone_formatted,
        "items": items_list,
        "totalAmount": total_price,
        "hasUpsell": order_data.get("hasUpsell", False),
        "upsellProduct": order_data.get("upsellProduct"),
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                settings.GOOGLE_SHEET_WEBHOOK_URL,
                json=sheets_payload,
                headers={"Content-Type": "application/json"},
                timeout=12.0,
                follow_redirects=True
            )
            print(f"📊 [Google Sheets Webhook] Sent Order #{order_id_formatted} -> Status {response.status_code}")
        except Exception as e:
            print(f"[Webhook Error] Failed to send to Google Sheets: {e}")


async def send_meta_capi(order_data: Dict[str, Any], client_ip: str, user_agent: str):
    if not settings.META_CAPI_TOKEN or not settings.META_PIXEL_ID:
        return

    url = f"https://graph.facebook.com/v19.0/{settings.META_PIXEL_ID}/events?access_token={settings.META_CAPI_TOKEN}"
    norm_phone = normalize_moroccan_phone(order_data.get("phoneNumber") or order_data.get("phone_number", ""))

    user_data = {
        "ph": [sha256_hash(norm_phone)],
        "fn": [sha256_hash(order_data.get("customerName") or order_data.get("customer_name", ""))],
        "client_ip_address": client_ip,
        "client_user_agent": user_agent,
        "country": [sha256_hash("ma")]
    }

    # Add MaxMind Geolocation if available for ultra-high Event Quality Match
    city = order_data.get("city")
    if city and city != "غير محدد":
        user_data["ct"] = [sha256_hash(city)]
    
    region = order_data.get("region")
    if region and region != "غير محدد":
        user_data["st"] = [sha256_hash(region)]

    payload = {
        "data": [{
            "event_name": "Purchase",
            "event_time": int(order_data.get("timestamp_unix", 1720000000)),
            "event_id": order_data.get("eventId"),
            "action_source": "website",
            "user_data": user_data,
            "custom_data": {
                "currency": "MAD",
                "value": float(order_data.get("totalAmount") or order_data.get("total_amount", 0.0)),
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
    norm_phone = normalize_moroccan_phone(order_data.get("phoneNumber") or order_data.get("phone_number", ""))

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
                "value": float(order_data.get("totalAmount") or order_data.get("total_amount", 0.0)),
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
    norm_phone = normalize_moroccan_phone(order_data.get("phoneNumber") or order_data.get("phone_number", ""))

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
            "price": str(float(order_data.get("totalAmount") or order_data.get("total_amount", 0.0))),
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

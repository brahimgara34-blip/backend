from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.analytics import ClickEvent
from app.schemas.analytics import ClickRecordRequest, ClickRecordResponse
from app.services.maxmind import lookup_maxmind_ip

router = APIRouter()


async def _process_and_save_click(
    path: str,
    referrer: str,
    session_id: str,
    client_ip: str,
    user_agent: str
):
    """
    Background worker to perform MaxMind / VPN lookup and persist click to database.
    """
    from app.core.database import AsyncSessionLocal
    try:
        geo = await lookup_maxmind_ip(client_ip)
        
        async with AsyncSessionLocal() as session:
            click = ClickEvent(
                path=path[:255],
                client_ip=client_ip[:50],
                country=geo.get("country", "MA")[:10],
                city=geo.get("city", "غير محدد")[:100],
                region=geo.get("region", "")[:100],
                is_proxy=geo.get("is_proxy", False),
                risk_score=geo.get("risk_score", 0.0),
                is_valid_morocco=geo.get("is_valid_morocco", True),
                referrer=(referrer or "")[:500],
                user_agent=user_agent[:1000] if user_agent else "",
                session_id=(session_id or "")[:100]
            )
            session.add(click)
            await session.commit()
    except Exception as e:
        print(f"[Analytics Click Error] {e}")


@router.post("/click", response_model=ClickRecordResponse)
async def record_click(
    payload: ClickRecordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    # 1. Extract Real Client IP
    client_ip = (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-real-ip")
        or request.headers.get("x-forwarded-for")
        or (request.client.host if request.client else "127.0.0.1")
    )
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    
    user_agent = request.headers.get("user-agent") or ""
    
    # 2. Schedule async DB write in background for instant response
    background_tasks.add_task(
        _process_and_save_click,
        path=payload.path or "/",
        referrer=payload.referrer or "",
        session_id=payload.session_id or "",
        client_ip=client_ip,
        user_agent=user_agent
    )

    return ClickRecordResponse(
        status="recorded",
        is_valid_morocco=True
    )

import httpx
from typing import Dict, Any, Optional
from app.core.config import settings


async def lookup_maxmind_ip(ip: str) -> Dict[str, Any]:
    """
    Look up IP location, ISP, and fraud/proxy traits using MaxMind GeoIP2 / Insights API.
    """
    result = {
        "city": "غير محدد",
        "region": "غير محدد",
        "country": "MA",
        "is_proxy": False,
        "risk_score": 0.0,
        "isp": "",
    }

    # Ignore localhost / private IP ranges
    if not ip or ip in ("127.0.0.1", "localhost", "::1") or ip.startswith("192.168.") or ip.startswith("10."):
        result["city"] = "الدار البيضاء (محلي)"
        result["region"] = "Casablanca-Settat"
        return result

    # Check if MaxMind credentials exist
    if not settings.MAXMIND_ACCOUNT_ID or not settings.MAXMIND_LICENSE_KEY:
        # Graceful default without credentials
        return result

    url = f"https://geoip.maxmind.com/geoip/v2.1/city/{ip}"

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(
                url,
                auth=(settings.MAXMIND_ACCOUNT_ID, settings.MAXMIND_LICENSE_KEY),
            )
            if response.status_code == 200:
                data = response.json()
                
                # City
                city_obj = data.get("city", {}).get("names", {})
                result["city"] = city_obj.get("en") or city_obj.get("fr") or "غير محدد"
                
                # Region / Subdivision
                subdivisions = data.get("subdivisions", [])
                if subdivisions:
                    sub_names = subdivisions[0].get("names", {})
                    result["region"] = sub_names.get("en") or sub_names.get("fr") or ""
                
                # Country
                result["country"] = data.get("country", {}).get("iso_code", "MA")

                # Traits & Proxy
                traits = data.get("traits", {})
                result["is_proxy"] = bool(
                    traits.get("is_anonymous_proxy") 
                    or traits.get("is_tor_exit_node") 
                    or traits.get("is_hosting_provider")
                )
                result["isp"] = traits.get("isp", "")
                result["risk_score"] = float(data.get("risk_score", 0.0))
            else:
                print(f"[MaxMind API Info] Status: {response.status_code}")
    except Exception as e:
        print(f"[MaxMind Lookup Error]: {e}")

    return result

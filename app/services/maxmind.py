import httpx
from typing import Dict, Any
from app.core.config import settings

# In-memory IP cache to avoid repeated external lookups for same IP (capped at 5000 IPs)
_IP_CACHE: Dict[str, Dict[str, Any]] = {}


async def lookup_maxmind_ip(ip: str) -> Dict[str, Any]:
    """
    Look up IP geolocation and perform multi-layer VPN / Proxy / Fraud detection.
    Determines if the visit is a genuine Moroccan visitor or a VPN/Proxy/Bot.
    """
    cleaned_ip = (ip or "").strip()
    
    # 1. Localhost / Private Subnets -> Clean Moroccan Test IP
    if not cleaned_ip or cleaned_ip in ("127.0.0.1", "localhost", "::1") or cleaned_ip.startswith("192.168.") or cleaned_ip.startswith("10.") or cleaned_ip.startswith("172.16."):
        return {
            "city": "الدار البيضاء (محلي)",
            "region": "Casablanca-Settat",
            "country": "MA",
            "is_proxy": False,
            "risk_score": 0.0,
            "isp": "Local Test Network",
            "is_valid_morocco": True,
        }

    # 2. Check Memory Cache
    if cleaned_ip in _IP_CACHE:
        return _IP_CACHE[cleaned_ip]

    result: Dict[str, Any] = {
        "city": "غير محدد",
        "region": "غير محدد",
        "country": "MA",
        "is_proxy": False,
        "risk_score": 0.0,
        "isp": "",
        "is_valid_morocco": True,
    }

    # 3. Layer 1: MaxMind GeoIP2 / Insights API (if configured)
    maxmind_success = False
    if settings.MAXMIND_ACCOUNT_ID and settings.MAXMIND_LICENSE_KEY:
        try:
            url = f"https://geoip.maxmind.com/geoip/v2.1/city/{cleaned_ip}"
            async with httpx.AsyncClient(timeout=3.5) as client:
                response = await client.get(
                    url,
                    auth=(settings.MAXMIND_ACCOUNT_ID, settings.MAXMIND_LICENSE_KEY),
                )
                if response.status_code == 200:
                    data = response.json()
                    city_obj = data.get("city", {}).get("names", {})
                    result["city"] = city_obj.get("en") or city_obj.get("fr") or "المغرب"
                    
                    subdivisions = data.get("subdivisions", [])
                    if subdivisions:
                        sub_names = subdivisions[0].get("names", {})
                        result["region"] = sub_names.get("en") or sub_names.get("fr") or ""
                    
                    result["country"] = data.get("country", {}).get("iso_code", "MA")
                    
                    traits = data.get("traits", {})
                    result["is_proxy"] = bool(
                        traits.get("is_anonymous_proxy") 
                        or traits.get("is_tor_exit_node") 
                        or traits.get("is_hosting_provider")
                        or traits.get("is_vpn")
                    )
                    result["isp"] = traits.get("isp", "")
                    result["risk_score"] = float(data.get("risk_score", 0.0))
                    maxmind_success = True
        except Exception as e:
            print(f"[MaxMind Lookup Error] {e}")

    # 4. Layer 2: Secondary Fast Fallback IP & Proxy/VPN Detection
    if not maxmind_success:
        try:
            # Query ip-api for geo + proxy/hosting detection
            url = f"http://ip-api.com/json/{cleaned_ip}?fields=status,message,country,countryCode,regionName,city,isp,org,as,proxy,hosting,mobile,query"
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    api_data = resp.json()
                    if api_data.get("status") == "success":
                        result["country"] = api_data.get("countryCode", "MA")
                        result["city"] = api_data.get("city", "المغرب")
                        result["region"] = api_data.get("regionName", "")
                        result["isp"] = api_data.get("isp") or api_data.get("org", "")
                        
                        # Proxy / Hosting / VPN Detection
                        is_proxy = bool(api_data.get("proxy", False) or api_data.get("hosting", False))
                        result["is_proxy"] = is_proxy
                        result["risk_score"] = 85.0 if is_proxy else 5.0
        except Exception as e:
            print(f"[Secondary IP Lookup Error] {e}")

    # 5. Determine Validity: Must be in Morocco (country == 'MA') AND NOT a Proxy/VPN AND risk_score below threshold
    is_morocco = (result.get("country") or "").upper() in ("MA", "MOROCCO", "MAROC")
    is_safe = not result.get("is_proxy", False) and float(result.get("risk_score", 0.0)) < settings.MAXMIND_RISK_THRESHOLD
    result["is_valid_morocco"] = bool(is_morocco and is_safe)

    # Cache result (limit cache size)
    if len(_IP_CACHE) > 5000:
        _IP_CACHE.clear()
    _IP_CACHE[cleaned_ip] = result

    return result

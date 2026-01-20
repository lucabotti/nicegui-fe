import os

import httpx

ORG_SVC_URL = os.getenv("ORG_SVC_URL", "http://org-svc:8001")


async def get_org_name(org_id: str) -> str:
    if not org_id:
        return "Unknown"
    async with httpx.AsyncClient() as client:
        try:
            # Note: in docker-compose, org-svc:8001 is accessible.
            # Local testing might need localhost:8001 if mapped.
            response = await client.get(f"{ORG_SVC_URL}/orgs/{org_id}")
            if response.status_code == 200:
                org_data = response.json()
                return org_data.get("name", "Unknown")
        except Exception:
            pass
    return "Unknown"

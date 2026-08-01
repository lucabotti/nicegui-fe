import os

import uvicorn
from fastapi import FastAPI

from .api.contacts import router as contact_router

app = FastAPI(title="Contact Service")

app.include_router(contact_router, prefix="/contacts", tags=["contacts"])


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8002))
    uvicorn.run(app, host="0.0.0.0", port=port)

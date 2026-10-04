import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("QIONGYU_HOST", "127.0.0.1"),
        port=int(os.environ.get("QIONGYU_PORT", "8001")),
        reload=False,
        log_level="info",
    )

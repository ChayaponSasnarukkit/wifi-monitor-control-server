from fastapi import Depends, FastAPI, Request
from typing import List, Optional
import uvicorn, asyncio, string, random
from fastapi.responses import StreamingResponse, FileResponse
app = FastAPI()


@app.get("/sim_api/{size}")
async def dump_data(size: int):
    return "a"*size

if __name__ == "__main__":
    config = uvicorn.Config(app, host="0.0.0.0", port=8088, workers=4, log_level="info")
    server = uvicorn.Server(config)
    server.run()
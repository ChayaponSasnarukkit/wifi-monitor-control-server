from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import sqlalchemy

from controller import scenario_controller, node_config_controller

app = FastAPI()

app.include_router(scenario_controller.router)
app.include_router(node_config_controller.router)

@app.exception_handler(sqlalchemy.exc.IntegrityError)
async def unicorn_exception_handler(request: Request, exc: sqlalchemy.exc.IntegrityError):
    return JSONResponse(
        status_code=400,
        content={"message": f"{str(exc).splitlines()[0]}"},
    )

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
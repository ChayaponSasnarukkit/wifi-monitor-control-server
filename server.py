from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import uvicorn, asyncio
import sqlalchemy
from controller import scenario_controller, node_config_controller, simulation_controller

@asynccontextmanager
async def lifespan(app: FastAPI):
    web_simulation_process = await asyncio.create_subprocess_shell("python -u ./simulation/server/web_application.py")
    file_simulation_process = await asyncio.create_subprocess_shell("python -u ./simulation/server/file_transfer.py")
    yield
    # Clean up the ML models and release the resources
    web_simulation_process.terminate()
    file_simulation_process.terminate()

app = FastAPI(lifespan=lifespan)

app.lock = asyncio.Lock()
app.running_task = None

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://localhost:3000/",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


print(app.running_task)
app.include_router(scenario_controller.router)
app.include_router(node_config_controller.router)
app.include_router(simulation_controller.router)

@app.exception_handler(sqlalchemy.exc.IntegrityError)
async def unicorn_exception_handler(request: Request, exc: sqlalchemy.exc.IntegrityError):
    return JSONResponse(
        status_code=400,
        content={"message": f"{str(exc).splitlines()[0]}"},
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
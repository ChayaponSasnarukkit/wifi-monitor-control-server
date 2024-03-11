from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import uvicorn, asyncio
import sqlalchemy, time, socket, threading
from utils.utils import _get_control_ip_address
from controller import scenario_controller, node_config_controller, simulation_controller

def send_time_sync_task(event):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind((_get_control_ip_address(), 8808))
    while True:
        if event.is_set():
            return
        udp_socket.sendto(f"{time.time():7f}".encode(), ("255.255.255.255", 8808))
        time.sleep(1)
    udp_socket.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # my_event = threading.Event()
    # loop = asyncio.get_running_loop()
    # udp_socket_thread = loop.run_in_executor(None, send_time_sync_task, my_event)
    web_simulation_process = await asyncio.create_subprocess_shell("python -u ./simulation/server/web_application.py")
    file_simulation_process = await asyncio.create_subprocess_shell("python -u ./simulation/server/file_transfer.py")
    yield
    # my_event.set()
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
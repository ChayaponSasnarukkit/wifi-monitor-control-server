from fastapi import Depends, FastAPI
import uvicorn

from controller import scenario_controller

app = FastAPI()

app.include_router(scenario_controller.router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
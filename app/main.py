from fastapi import FastAPI
from pathlib import Path

import sys
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
from database import Base,engine
from models import Task
# Add the parent directory of this file to PYTHONPATH
import uvicorn
from routers import router
app = FastAPI()

app.include_router(router)
@app.on_event("startup")
def startup():
    # Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
if __name__=="__main__":
    uvicorn.run(app=app,host="0.0.0.0",port=8000)



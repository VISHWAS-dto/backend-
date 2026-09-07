from fastapi import FastAPI

app = FastAPI(title="catalyx-backend-py")


@app.get("/")
def health_check():
    return {"status": "ok", "message": "catalyx-backend-py is running"}

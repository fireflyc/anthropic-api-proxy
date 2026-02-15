import uvicorn

if __name__ == "__main__":

    uvicorn.run(
        "anthropic_api_proxy.main:app",
        host="0.0.0.0",
        port=8080
    )
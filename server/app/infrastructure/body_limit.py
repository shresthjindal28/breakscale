from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes: int = 262144):
        self.app, self.max_bytes = app, max_bytes
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope,receive,send)
        chunks = []
        size = 0
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            body = event.get("body",b"")
            size += len(body)
            if size > self.max_bytes:
                return await JSONResponse({"detail":"Request body too large"},status_code=413)(scope,receive,send)
            chunks.append(body)
            if not event.get("more_body",False):
                break
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type":"http.request","body":b"".join(chunks),"more_body":False}
        await self.app(scope,bounded_receive,send)

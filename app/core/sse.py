import asyncio
from collections.abc import AsyncIterator

# SSE 주석 라인. ':'로 시작하는 줄은 클라이언트가 이벤트로 처리하지 않는다
HEARTBEAT = ": ping\n\n"

_DONE = object()


async def with_heartbeat(stream: AsyncIterator[str], interval: float) -> AsyncIterator[str]:
    """stream이 interval초 동안 아무것도 내보내지 않으면 하트비트를 끼워 넣는다.

    Vercel rewrite 프록시는 백엔드에서 120초 동안 바이트가 없으면 연결을 끊는다.
    AI 서버가 검색·생성 중에 오래 조용해도 연결이 유지되도록 주기적으로 바이트를 흘려보낸다.

    stream은 별도 task 하나에서 끝까지 돌린다 — 매번 wait_for(anext())로 기다리면
    timeout 때 stream 자체가 취소돼 버린다.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=1)

    async def produce() -> None:
        try:
            async for chunk in stream:
                await queue.put(chunk)
        except Exception as e:
            await queue.put(e)
            return
        await queue.put(_DONE)

    producer = asyncio.create_task(produce())
    getter: asyncio.Task | None = None
    try:
        while True:
            # get task를 timeout마다 새로 만들지 않고 유지한다 — wait_for로 취소하면
            # 취소 직전에 꺼낸 chunk가 유실될 수 있다
            if getter is None:
                getter = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({getter}, timeout=interval)  #interval동안 done, pending(-)인 task
            if not done:
                yield HEARTBEAT 
                continue   #ping 보내고 다시 대기
            item = getter.result()
            getter = None
            if item is _DONE:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        # 클라이언트가 끊으면 여기로 온다. stream 쪽 finally(DB 정리 등)가 돌도록 취소를 전파한다
        if getter is not None:
            getter.cancel()
        producer.cancel()
        try:
            await producer
        except asyncio.CancelledError:
            pass

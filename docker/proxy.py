"""HTTPS allow-list proxy: CONNECT tunnels only to the agent's model API. Everything else gets 403."""
import asyncio
import os
import sys

ALLOWED = {h.strip() for h in os.environ.get("ALLOWED_HOSTS", "api.anthropic.com").split(",") if h.strip()}


async def pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


async def handle(reader, writer):
    try:
        request = await reader.readuntil(b"\r\n\r\n")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        writer.close()
        return
    line = request.split(b"\r\n", 1)[0].decode(errors="replace")
    parts = line.split()
    host, port = None, 443
    if len(parts) >= 2 and parts[0] == "CONNECT":
        host, _, p = parts[1].rpartition(":")
        port = int(p or 443)
    if host not in ALLOWED or port != 443:
        print(f"DENY {line}", flush=True)
        writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        writer.close()
        return
    print(f"ALLOW {host}:{port}", flush=True)
    try:
        up_reader, up_writer = await asyncio.open_connection(host, port)
    except OSError:
        writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        writer.close()
        return
    writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
    await writer.drain()
    await asyncio.gather(pipe(reader, up_writer), pipe(up_reader, writer))


async def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3128
    server = await asyncio.start_server(handle, "0.0.0.0", port)
    print(f"proxy on :{port}, allowed: {sorted(ALLOWED)}", flush=True)
    async with server:
        await server.serve_forever()


asyncio.run(main())

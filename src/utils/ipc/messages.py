import asyncio
import msgspec

class Publish(msgspec.Struct, tag = True):
    pair: str

class Subscribe(msgspec.Struct, tag = True):
    pair: str

class Ready(msgspec.Struct, tag = True):
    pass

class Text(msgspec.Struct, tag = True):
    text: str
    final: bool

Request = Publish | Subscribe | Ready | Text

RequestEncoder = msgspec.msgpack.Encoder()
RequestDecoder = msgspec.msgpack.Decoder(Request)

async def receive_request(reader: asyncio.StreamReader) -> Request:
    len = int.from_bytes(await reader.readexactly(4), "big")
    if len < 0 or len > 1024:
        raise asyncio.InvalidStateError()
    data = await reader.readexactly(len)
    return RequestDecoder.decode(data)

async def send_request(writer, req):
    data = RequestEncoder.encode(req)
    writer.write(len(data).to_bytes(4, "big"))
    writer.write(data)
    await writer.drain()
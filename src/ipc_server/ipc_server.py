import asyncio
from utils.ipc import messages

Publishers: dict[str, asyncio.StreamReader] = {}
Subscribers: dict[str, bool] = {}

PublisherAppear = asyncio.Condition()
SubscriberAppear = asyncio.Condition()


async def AddPublisher(pair: str, reader: asyncio.StreamReader):
    async with PublisherAppear:
        if pair in Publishers:
            Publishers[pair] = None
        else:
            Publishers[pair] = reader

        PublisherAppear.notify_all()


async def RemovePublisher(pair: str):
    async with PublisherAppear:
        if pair in Publishers:
            del Publishers[pair]


async def AddSubscriber(pair: str):
    async with SubscriberAppear:
        Subscribers[pair] = pair not in Subscribers
        SubscriberAppear.notify_all()


async def RemoveSubscriber(pair: str):
    async with SubscriberAppear:
        if pair in Subscribers:
            del Subscribers[pair]


async def wait_for_publisher(pair: str, timeout: float = 10.0):
    async def waiter():
        async with PublisherAppear:
            await PublisherAppear.wait_for(lambda: pair in Publishers)
            return Publishers[pair]

    return await asyncio.wait_for(waiter(), timeout)


async def wait_for_subscriber(pair: str, timeout: float = 10.0):
    async def waiter():
        async with SubscriberAppear:
            await SubscriberAppear.wait_for(lambda: pair in Subscribers)
            return Subscribers[pair]

    return await asyncio.wait_for(waiter(), timeout)


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    while not reader.at_eof():
        writer.write(await reader.read(1024))
        await writer.drain()


async def handle_publish(
    pair: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
):
    await AddPublisher(pair, reader)
    try:
        await wait_for_subscriber(pair)
        await messages.send_request(writer, messages.Ready())

    except Exception as e:
        await RemovePublisher(pair)
        writer.close()


async def handle_subscribe(pair: str, writer: asyncio.StreamWriter):
    await AddSubscriber(pair)

    try:
        publisher = await wait_for_publisher(pair)
        await messages.send_request(writer, messages.Ready())
        await pipe(publisher, writer)
    except Exception as e:
        pass
    finally:
        await RemovePublisher(pair)
        await RemoveSubscriber(pair)
        writer.close()


async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        req = await messages.receive_request(reader)
        match req:
            case messages.Publish(pair):
                await handle_publish(pair, reader, writer)
            case messages.Subscribe(pair):
                await handle_subscribe(pair, writer)
            case _:
                raise asyncio.InvalidStateError()
    except Exception as e:
        writer.close()


async def run_ipc_server(host, port):
    server = await asyncio.start_server(handle_connection, host, port)
    async with server:
        await server.serve_forever()


def start_ipc_server(host="localhost", port=3015):
    asyncio.run(run_ipc_server(host, port))


if __name__ == "__main__":
    start_ipc_server()

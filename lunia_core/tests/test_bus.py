from app.core.bus.redis_bus import RedisBus, RedisBusConfig


def test_bus_publish_subscribe_in_memory():
    config = RedisBusConfig(enabled=False)
    bus = RedisBus(config=config)
    received = []

    def handler(message):
        received.append(message)

    bus.subscribe("signals", handler)
    bus.publish("signals", {"symbol": "BTCUSDT"})

    assert received == [{"symbol": "BTCUSDT"}]

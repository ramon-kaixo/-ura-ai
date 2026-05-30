import logging
from typing import Any

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

logger = logging.getLogger("IoTListener")


class IoTListener:
    def __init__(self, bus: Any, host: str = "localhost", port: int = 1883) -> None:
        if mqtt is None:
            raise ImportError("paho-mqtt not installed. Run: pip install paho-mqtt")
        self.bus = bus
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(host, port, 60)
        self.client.loop_start()

    def on_connect(self, client: Any, userdata: Any, flags: Any, rc: Any) -> None:
        client.subscribe("almacen/puerta")
        client.subscribe("nevera/temperatura")

    def on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        payload = msg.payload.decode()
        if msg.topic == "almacen/puerta":
            self.bus.publicar("eventos/puerta_almacen", {"estado": payload})
        elif msg.topic == "nevera/temperatura":
            try:
                temp = float(payload)
                if temp > 5:
                    self.bus.publicar("eventos/alerta_temperatura", {"temp": temp})
            except ValueError:
                logger.error("Invalid temperature value: %s", payload)

"""Implementação de IMessageBroker usando aio-pika."""

import asyncio
import json
import logging
import os
from typing import Any, Callable, Awaitable
from datetime import datetime, timezone

import aio_pika
from aio_pika import Message, DeliveryMode

from src.domain.repositories.interfaces import IMessageBroker
from src.config.settings import settings

logger = logging.getLogger("pharma.infrastructure.broker")

EXCHANGE_DIRECT = "pharma.direct"
EXCHANGE_EVENTS = "pharma.events"

QUEUE_ANALYZE      = "pharma.analyze"
QUEUE_INTERACTIONS = "pharma.interactions"
QUEUE_PRESCRIPTION = "pharma.prescription"
QUEUE_RESULTS      = "pharma.results"

ALL_QUEUES = [QUEUE_ANALYZE, QUEUE_INTERACTIONS, QUEUE_PRESCRIPTION, QUEUE_RESULTS]


class RabbitMQBroker(IMessageBroker):
    """Implementação de IMessageBroker com RabbitMQ via aio-pika."""

    def __init__(self) -> None:
        self._conn = None
        self._pub_channel = None
        self._direct_exchange = None
        self._events_exchange = None

    async def connect(self) -> None:
        logger.info("Conectando ao RabbitMQ: %s", settings.rabbitmq_url)
        self._conn = await aio_pika.connect_robust(settings.rabbitmq_url)
        self._pub_channel = await self._conn.channel()

        self._direct_exchange = await self._pub_channel.declare_exchange(
            EXCHANGE_DIRECT, aio_pika.ExchangeType.DIRECT, durable=True
        )
        self._events_exchange = await self._pub_channel.declare_exchange(
            EXCHANGE_EVENTS, aio_pika.ExchangeType.FANOUT, durable=True
        )

        for q_name in ALL_QUEUES:
            q = await self._pub_channel.declare_queue(
                q_name, durable=True,
                arguments={"x-message-ttl": 3_600_000, "x-dead-letter-exchange": f"{q_name}.dlx"},
            )
            await q.bind(self._direct_exchange, routing_key=q_name)

        logger.info("RabbitMQ pronto. Filas: %s", ALL_QUEUES)

    async def disconnect(self) -> None:
        if self._conn:
            await self._conn.close()
            logger.info("RabbitMQ desconectado")

    async def publish(self, queue: str, payload: dict, priority: int = 0) -> None:
        if not self._direct_exchange:
            raise RuntimeError("Broker não conectado")
        body = json.dumps(payload, default=str).encode()
        msg = Message(
            body,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            priority=priority,
            timestamp=datetime.now(timezone.utc),
        )
        await self._direct_exchange.publish(msg, routing_key=queue)

    async def publish_event(self, event: dict) -> None:
        if not self._events_exchange:
            return
        body = json.dumps(event, default=str).encode()
        msg = Message(body, delivery_mode=DeliveryMode.NOT_PERSISTENT, content_type="application/json")
        await self._events_exchange.publish(msg, routing_key="")

    async def consume(self, queue: str, handler: Callable[[dict], Awaitable[None]], prefetch: int = 1) -> None:
        if not self._conn:
            raise RuntimeError("Broker não conectado")
        channel = await self._conn.channel()
        await channel.set_qos(prefetch_count=prefetch)
        exchange = await channel.declare_exchange(EXCHANGE_DIRECT, aio_pika.ExchangeType.DIRECT, durable=True)
        q = await channel.declare_queue(queue, durable=True)
        await q.bind(exchange, routing_key=queue)

        logger.info("Consumindo: %s (prefetch=%d)", queue, prefetch)
        async with q.iterator() as messages:
            async for message in messages:
                try:
                    payload = json.loads(message.body)
                    await handler(payload)
                    await message.ack()
                except Exception as exc:
                    logger.error("Falha em %s: %s", queue, exc)
                    deaths = message.headers.get("x-death", [])
                    count = deaths[0].get("count", 0) if deaths else 0
                    await message.nack(requeue=count < 3)


broker = RabbitMQBroker()

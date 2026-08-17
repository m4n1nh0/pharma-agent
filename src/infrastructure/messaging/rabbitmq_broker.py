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


def dlx_name(queue: str) -> str:
    return f"{queue}.dlx"


def dlq_name(queue: str) -> str:
    return f"{queue}.dlq"


def queue_args(queue: str) -> dict:
    """Argumentos de declaração da fila — fonte única.

    O RabbitMQ rejeita redeclarar uma fila com argumentos diferentes
    (PRECONDITION_FAILED), e API e worker declaram as mesmas filas em processos
    distintos. Divergir aqui derruba o consumidor.
    """
    return {"x-message-ttl": 3_600_000, "x-dead-letter-exchange": dlx_name(queue)}


class RabbitMQBroker(IMessageBroker):
    """Implementação de IMessageBroker com RabbitMQ via aio-pika.

    Degrada para despacho in-process quando o RabbitMQ não está disponível
    (deploy single-service, ex. Railway sem addon): `publish` chama o handler
    registrado em `consume` numa task local, em vez de falhar.
    """

    def __init__(self) -> None:
        self._conn = None
        self._pub_channel = None
        self._direct_exchange = None
        self._events_exchange = None
        self._local_handlers: dict[str, Callable[[dict], Awaitable[None]]] = {}
        self._local_tasks: set[asyncio.Task] = set()

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and not self._conn.is_closed

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
            # DLX + DLQ antes da fila: sem o exchange de dead-letter existindo, o
            # x-dead-letter-exchange aponta para o nada e a mensagem descartada
            # desaparece em silêncio em vez de ficar inspecionável.
            dlx = await self._pub_channel.declare_exchange(
                dlx_name(q_name), aio_pika.ExchangeType.FANOUT, durable=True
            )
            dlq = await self._pub_channel.declare_queue(dlq_name(q_name), durable=True)
            await dlq.bind(dlx)

            q = await self._pub_channel.declare_queue(
                q_name, durable=True, arguments=queue_args(q_name)
            )
            await q.bind(self._direct_exchange, routing_key=q_name)

        logger.info("RabbitMQ pronto. Filas: %s (+ .dlq)", ALL_QUEUES)

    async def disconnect(self) -> None:
        if self._conn:
            await self._conn.close()
            logger.info("RabbitMQ desconectado")

    async def publish(self, queue: str, payload: dict, priority: int = 0) -> None:
        if not self._direct_exchange:
            return await self._publish_local(queue, payload)
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
        self._local_handlers[queue] = handler
        if not self._conn:
            # Sem RabbitMQ: fica registrado como handler local e `publish` despacha direto.
            logger.warning("Sem conexão — %s será processada in-process (sem fila durável)", queue)
            return
        channel = await self._conn.channel()
        await channel.set_qos(prefetch_count=prefetch)
        exchange = await channel.declare_exchange(EXCHANGE_DIRECT, aio_pika.ExchangeType.DIRECT, durable=True)
        # Mesmos argumentos usados em connect(): declaração divergente é rejeitada
        # com PRECONDITION_FAILED e o consumidor morre sem consumir nada.
        q = await channel.declare_queue(queue, durable=True, arguments=queue_args(queue))
        await q.bind(exchange, routing_key=queue)

        logger.info("Consumindo: %s (prefetch=%d)", queue, prefetch)
        async with q.iterator() as messages:
            async for message in messages:
                try:
                    payload = json.loads(message.body)
                    await handler(payload)
                    await message.ack()
                except Exception as exc:
                    # Uma única retentativa, decidida por `redelivered`.
                    # Não use x-death para contar aqui: esse header só aparece
                    # quando a mensagem passa pelo dead-letter, então com
                    # requeue=True ele nunca existe e o contador ficaria preso em
                    # zero — requeue infinito, reprocessando a análise para sempre.
                    retry = not message.redelivered
                    logger.error(
                        "Falha em %s (%s): %s",
                        queue, "vai reprocessar" if retry else "→ DLQ", exc,
                    )
                    await message.nack(requeue=retry)

    # ── Fallback in-process ───────────────────────────────────────────────────
    async def _publish_local(self, queue: str, payload: dict) -> None:
        """Executa o handler da fila numa task local (sem RabbitMQ).

        Mantém referência forte à task: sem isso o GC pode coletá-la no meio da
        execução, já que `create_task` não guarda referência própria.
        """
        handler = self._local_handlers.get(queue)
        if not handler:
            raise RuntimeError(
                f"Fila '{queue}' sem broker e sem handler local — "
                "verifique EMBEDDED_WORKER e RABBITMQ_URL"
            )
        task = asyncio.create_task(self._run_local(queue, handler, payload))
        self._local_tasks.add(task)
        task.add_done_callback(self._local_tasks.discard)

    @staticmethod
    async def _run_local(queue: str, handler: Callable[[dict], Awaitable[None]], payload: dict) -> None:
        try:
            await handler(payload)
        except Exception as exc:
            # O handler já marcou o job como failed; aqui só evitamos exceção órfã na task.
            logger.error("Falha no processamento local de %s: %s", queue, exc)


broker = RabbitMQBroker()

"""P1-3: Produce 5 JSON messages to `ods_ue_signal`, consume them back from earliest."""
import json
import uuid

import pytest
from kafka import KafkaConsumer, KafkaProducer


@pytest.mark.infra
def test_p1_3_kafka_produce_consume_ods_ue_signal():
    topic = "ods_ue_signal"
    group_id = f"test-{uuid.uuid4().hex[:8]}"
    messages = [
        {"imsi": f"46000{i:010d}", "cell_id": "cell_001", "rsrp": -90 - i, "sinr": 15 - i}
        for i in range(5)
    ]

    producer = KafkaProducer(
        bootstrap_servers="localhost:19092",
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
    )
    for msg in messages:
        producer.send(topic, msg)
    producer.flush()
    producer.close()

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers="localhost:19092",
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        consumer_timeout_ms=10_000,
    )
    received = []
    for record in consumer:
        received.append(record.value)
        if len(received) >= 5:
            break
    consumer.close()

    assert len(received) == 5, f"expected 5 messages, got {len(received)}: {received!r}"
    # Match by IMSI rather than order (different partitions can interleave).
    sent_imsis = {m["imsi"] for m in messages}
    received_imsis = {m["imsi"] for m in received}
    assert sent_imsis == received_imsis

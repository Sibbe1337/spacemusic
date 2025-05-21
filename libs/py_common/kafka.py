# libs/py_common/kafka.py
import os
import socket
import structlog
from confluent_kafka import Producer, Consumer, KafkaError, KafkaException
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer, AvroDeserializer
from confluent_kafka.serialization import StringSerializer, StringDeserializer

logger = structlog.get_logger(__name__)

# --- Environment Variables for Kafka Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081")

# Common Kafka client configuration
# For mTLS, you'd set: ssl.ca.location, ssl.certificate.location, ssl.key.location, security.protocol=SSL
# These would come from env vars like MSK_SSL_CA_LOCATION, MSK_SSL_CERT_LOCATION, MSK_SSL_KEY_LOCATION
# and MSK_SECURITY_PROTOCOL or similar.

kafka_common_config = {
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    # "client.id": socket.gethostname(), # Useful for server-side logging
    # SSL/TLS configuration (example for MSK IAM or standard TLS)
    # "security.protocol": os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"), 
    # "ssl.ca.location": os.getenv("KAFKA_SSL_CA_LOCATION"),
    # "ssl.certificate.location": os.getenv("KAFKA_SSL_CERTIFICATE_LOCATION"),
    # "ssl.key.location": os.getenv("KAFKA_SSL_KEY_LOCATION"),
}

# Remove None values from config as confluent-kafka client expects existing paths for certs
kafka_config = {k: v for k, v in kafka_common_config.items() if v is not None}

if kafka_config.get("security.protocol", "PLAINTEXT").upper() in ["SASL_SSL", "SSL"]:
    if not kafka_config.get("ssl.ca.location") and not os.getenv("KAFKA_SKIP_SSL_VERIFICATION_FOR_DEV"): # For local dev without proper certs
        logger.warning("Kafka SSL CA location not set and KAFKA_SKIP_SSL_VERIFICATION_FOR_DEV is not true. SSL might fail.")
        # For actual mTLS, cert and key locations would also be checked.

# --- Schema Registry Client ---
_schema_registry_client = None
def get_schema_registry_client():
    global _schema_registry_client
    if _schema_registry_client is None:
        if not SCHEMA_REGISTRY_URL:
            logger.error("SCHEMA_REGISTRY_URL is not set. Cannot create Avro Producer/Consumer.")
            raise ValueError("SCHEMA_REGISTRY_URL is required for Avro operations.")
        sr_config = {'url': SCHEMA_REGISTRY_URL}
        _schema_registry_client = SchemaRegistryClient(sr_config)
    return _schema_registry_client

# --- Producer Helper ---
def create_producer(config_overrides: dict = None) -> Producer:
    producer_config = kafka_config.copy()
    if config_overrides:
        producer_config.update(config_overrides)
    
    logger.info("Creating Kafka Producer", config=producer_config)
    return Producer(producer_config)

def create_avro_producer(value_schema_str: str, key_schema_str: str = None, config_overrides: dict = None) -> Producer:
    sr_client = get_schema_registry_client()
    
    avro_serializer_config = {
        'auto.register.schemas': True # Consider False for production for more control
    }
    value_avro_serializer = AvroSerializer(sr_client, value_schema_str, conf=avro_serializer_config)
    
    key_serializer = StringSerializer('utf_8')
    if key_schema_str: # If key is also Avro
        key_avro_serializer = AvroSerializer(sr_client, key_schema_str, conf=avro_serializer_config)
        key_serializer = key_avro_serializer
        
    producer_config = kafka_config.copy()
    producer_config.update({
        'key.serializer': key_serializer,
        'value.serializer': value_avro_serializer
    })
    if config_overrides:
        producer_config.update(config_overrides)

    logger.info("Creating Avro Kafka Producer", config=producer_config)
    # Note: confluent_kafka.avro.AvroProducer is deprecated. Use Producer with AvroSerializer.
    return Producer(producer_config)

# --- Consumer Helper ---
def create_consumer(group_id: str, topics: list[str], config_overrides: dict = None, auto_offset_reset='earliest') -> Consumer:
    consumer_config = kafka_config.copy()
    consumer_config.update({
        'group.id': group_id,
        'auto.offset.reset': auto_offset_reset,
        'enable.auto.commit': False # Recommended for more control over commits
    })
    if config_overrides:
        consumer_config.update(config_overrides)
    
    logger.info("Creating Kafka Consumer", config=consumer_config, topics=topics)
    consumer = Consumer(consumer_config)
    consumer.subscribe(topics)
    return consumer

def create_avro_consumer(group_id: str, topics: list[str], value_schema_str: str, key_schema_str: str = None, config_overrides: dict = None, auto_offset_reset='earliest') -> Consumer:
    sr_client = get_schema_registry_client()
    
    value_avro_deserializer = AvroDeserializer(sr_client, value_schema_str)
    key_deserializer = StringDeserializer('utf_8')
    if key_schema_str:
        key_avro_deserializer = AvroDeserializer(sr_client, key_schema_str)
        key_deserializer = key_avro_deserializer

    consumer_config = kafka_config.copy()
    consumer_config.update({
        'group.id': group_id,
        'auto.offset.reset': auto_offset_reset,
        'enable.auto.commit': False,
        'key.deserializer': key_deserializer,
        'value.deserializer': value_avro_deserializer
    })
    if config_overrides:
        consumer_config.update(config_overrides)

    logger.info("Creating Avro Kafka Consumer", config=consumer_config, topics=topics)
    # Note: confluent_kafka.avro.AvroConsumer is deprecated. Use Consumer with AvroDeserializer.
    consumer = Consumer(consumer_config)
    consumer.subscribe(topics)
    return consumer

# --- Delivery Report Callback (Example for Producer) ---
def delivery_report(err, msg):
    """ Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush(). """
    if err is not None:
        logger.error('Message delivery failed', topic=msg.topic(), partition=msg.partition(), error=str(err))
    else:
        logger.debug('Message delivered', topic=msg.topic(), partition=msg.partition(), offset=msg.offset())

logger.info("Kafka common library loaded.", bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS, schema_registry_url=SCHEMA_REGISTRY_URL) 
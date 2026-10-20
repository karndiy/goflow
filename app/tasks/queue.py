from redis import Redis
from rq import Queue

from app.core.config import get_settings

settings = get_settings()

redis_conn = Redis.from_url(settings.redis_url)
publishing_queue = Queue("publishing", connection=redis_conn)
generation_queue = Queue("content_generation", connection=redis_conn)

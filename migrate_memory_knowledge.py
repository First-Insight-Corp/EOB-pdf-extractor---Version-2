import logging

from agents.memory import bootstrap_learning_memory_to_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    # In DB-only mode this is retained as a compatibility command.
    count = bootstrap_learning_memory_to_db(force_upsert=True, log_details=True)
    logger.info(
        "Knowledge memory filesystem migration is deprecated in DB-only mode. "
        f"Imported/updated {count} records."
    )

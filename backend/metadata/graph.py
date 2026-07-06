"""Neo4j driver singleton + thin query helper."""
from functools import lru_cache
from collections.abc import Callable
from typing import Any

from neo4j import Driver, GraphDatabase

from backend.config import get_settings


@lru_cache(maxsize=1)
def get_driver() -> Driver:
    s = get_settings()
    driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    driver.verify_connectivity()
    return driver


def run_query(cypher: str, **params: Any) -> list[dict]:
    """Execute a Cypher query and return all records as plain dicts."""
    driver = get_driver()
    with driver.session(database=get_settings().neo4j_database) as session:
        result = session.run(cypher, params)
        return [dict(record) for record in result]


def run_write_transaction(work: Callable[[Any], Any]) -> Any:
    """Execute a write callback in one Neo4j transaction."""
    driver = get_driver()
    with driver.session(database=get_settings().neo4j_database) as session:
        return session.execute_write(lambda tx: work(tx))


def close_driver() -> None:
    """Close the singleton driver if it exists. Idempotent."""
    info = get_driver.cache_info()
    if info.currsize == 0:
        return
    get_driver().close()
    get_driver.cache_clear()

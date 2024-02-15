import logging

from tracardi.config import tracardi
from tracardi.domain.test import Test
from tracardi.exceptions.log_handler import log_handler
from tracardi.service.storage.mysql.mapping.test_mapping import map_to_test_table
from tracardi.service.storage.mysql.schema.table import TestTable
from tracardi.service.storage.mysql.service.table_service import TableService
from tracardi.service.storage.mysql.service.table_filtering import where_with_context
from tracardi.service.storage.mysql.utils.select_result import SelectResult

logger = logging.getLogger(__name__)
logger.setLevel(tracardi.logging_level)
logger.addHandler(log_handler)


def _where_with_context(*clause):
    return where_with_context(
        TestTable,
        False,
        *clause
    )

class TestService(TableService):

    async def load_all(self, search: str = None, limit: int = None, offset: int = None) -> SelectResult:
        if search:
            where = _where_with_context(
                TestTable.name.like(f'%{search}%')
            )
        else:
            where = _where_with_context()

        return await self._select_query(TestTable,
                                        where=where,
                                        order_by=TestTable.name,
                                        limit=limit,
                                        offset=offset)


    async def load_by_id(self, test_id: str) -> SelectResult:
        return await self._load_by_id(TestTable, primary_id=test_id, server_context=False)

    async def delete_by_id(self, test_id: str) -> tuple:
        return await self._delete_by_id(TestTable,
                                        primary_id=test_id,
                                        server_context=False)

    async def upsert(self, test: Test):
        return await self._replace(TestTable, map_to_test_table(test))


    
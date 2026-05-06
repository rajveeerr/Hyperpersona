"""Orders service — list paginated order history for a customer.

`POST /checkout` and `orders_put` are M3 territory; this milestone only
ships the read endpoint.
"""

from __future__ import annotations

from shared.dynamo import DynamoClient

from ..schemas.orders import OrderListResponse, OrderSummary


def _strip_dynamo_keys(item: dict) -> dict:
    out = dict(item)
    out.pop("PK", None)
    out.pop("SK", None)
    return out


class OrdersService:
    def __init__(self, dynamo: DynamoClient) -> None:
        self._dynamo = dynamo

    def list_orders(
        self,
        customer_id: str,
        page: int,
        page_size: int,
    ) -> OrderListResponse:
        rows = self._dynamo.orders_list(customer_id)
        # Newest first by placedAt (camelCase from Dynamo writes).
        rows.sort(key=lambda r: r.get("placedAt") or r.get("placed_at") or "", reverse=True)

        total = len(rows)
        page = max(1, page)
        page_size = min(50, max(1, page_size))
        start = (page - 1) * page_size
        page_rows = rows[start : start + page_size]

        items = [OrderSummary.model_validate(_strip_dynamo_keys(r)) for r in page_rows]
        return OrderListResponse(items=items, page=page, pageSize=page_size, total=total)

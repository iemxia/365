from fastapi import APIRouter
import sqlalchemy
from src import database as db
metadata_obj = sqlalchemy.MetaData()

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """
    res = []
    with db.engine.begin() as connection:
        potion_rows = connection.execute(sqlalchemy.text("SELECT id, potion_sku, potion_type, price FROM potions"))
        for row in potion_rows:
            id, sku, potion_type, price = row
            quantity = connection.execute(sqlalchemy.text("SELECT SUM(quantity_change) FROM potions_ledger_entries WHERE potion_id = :pot_id"), {"pot_id": id}).scalar_one()
            if quantity != None and quantity > 0:
                res.append(
                    {
                            "sku": sku,
                            "name": sku,
                            "quantity": quantity,
                            "price": price,
                            #[r, g, b, d]
                            "potion_type": potion_type
                        }
                )
        return res

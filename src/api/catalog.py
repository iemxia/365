from fastapi import APIRouter
import sqlalchemy
from src import database as db


router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """
    res = []
    with db.engine.begin() as connection:
        potion_rows = connection.execute(sqlalchemy.text("SELECT potion_sku, green_ml, red_ml, blue_ml, dark_ml, price, quantity FROM potions"))
        for row in potion_rows:
            sku, green_ml, red_ml, blue_ml, dark_ml, price, quantity = row
            if quantity > 0:
                res.append(
                    {
                            "sku": sku,
                            "name": sku,
                            "quantity": quantity,
                            "price": price,
                            #[r, g, b, d]
                            "potion_type": [green_ml, red_ml, blue_ml, dark_ml],
                        }
                )
        return res

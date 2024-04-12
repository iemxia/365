from fastapi import APIRouter
import sqlalchemy
from src import database as db


router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """
    
    with db.engine.begin() as connection:
        num_green = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).scalar_one()
        num_red = connection.execute(sqlalchemy.text("SELECT num_red_potions FROM global_inventory")).scalar_one()
        num_blue = connection.execute(sqlalchemy.text("SELECT num_blue_potions FROM global_inventory")).scalar_one()
        res = []
        if num_red > 1:
            res.append(
                    {
                        "sku": "RED_POTION_0",
                        "name": "red potion",
                        "quantity": num_red,
                        "price": 45,
                        #[r, g, b, d]
                        "potion_type": [100, 0, 0, 0],
                    }
            )
        if num_green > 1:
            res.append(
                    {
                        "sku": "GREEN_POTION_0",
                        "name": "green potion",
                        "quantity": num_green,
                        "price": 50,
                        #[r, g, b, d]
                        "potion_type": [0, 100, 0, 0],
                    }
            )
        if num_blue > 1:
            res.append(
                    {
                        "sku": "BLUE_POTION_0",
                        "name": "blue potion",
                        "quantity": num_blue,
                        "price": 65,
                        #[r, g, b, d]
                        "potion_type": [0, 0, 100, 0],
                    }
            )
        return res

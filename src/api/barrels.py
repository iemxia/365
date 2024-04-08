from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)

class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    """ """
    total_green_ml = 0
    total_price = 0
    for barrel in barrels_delivered:
        total_green_ml += (barrel.ml_per_barrel * barrel.quantity)
        total_price += barrel.price
    with db.engine.begin() as connection:
        # update mL of green
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_green_ml = num_green_ml + {total_green_ml}'))
        # update gold left
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET gold = gold - {total_price}'))
    print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)
    with db.engine.begin() as connection:
        # get the number of potions
        green_potions_num = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).scalar_one()
        if green_potions_num < 10:
            return [
                {
                    "sku": "SMALL_GREEN_BARREL",
                    "quantity": 2,
                }
            ]
        else:  # not buying anything
            return []


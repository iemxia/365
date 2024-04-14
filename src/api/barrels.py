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
    total_blue_ml = 0
    total_red_ml = 0
    total_price = 0
    for barrel in barrels_delivered:
        if "GREEN" in barrel.sku:
            total_green_ml += (barrel.ml_per_barrel * barrel.quantity)
        elif "RED" in barrel.sku:
            total_red_ml += (barrel.ml_per_barrel * barrel.quantity)
        elif "BLUE" in barrel.sku:
            total_blue_ml += (barrel.ml_per_barrel * barrel.quantity)
        total_price += (barrel.price * barrel.quantity)
    with db.engine.begin() as connection:
        # update mL of green
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_green_ml = num_green_ml + {total_green_ml}'))
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_red_ml = num_red_ml + {total_red_ml}'))
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_blue_ml = num_blue_ml + {total_blue_ml}'))
        # update gold left
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET gold = gold - {total_price}'))
    print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")
    return "OK"

# Gets called once a day
# log the wholesale catalog and look for pattern
# SMALL_GREEN and SMALL_RED barrels: 500 mL and cost 100 gold
# SMALL_BLUE: 500 mL cost 120 gold
# MEDIUM_RED and GREEN: 2500 mL cost 250 gold
# MEDIUM_BLUE: 2500 mL cost 300 gold
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)
    with db.engine.begin() as connection:
        # get the number of potions
        green_potions_num = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).scalar_one()
        blue_potions_num = connection.execute(sqlalchemy.text("SELECT num_blue_potions FROM global_inventory")).scalar_one()
        red_potions_num = connection.execute(sqlalchemy.text("SELECT num_red_potions FROM global_inventory")).scalar_one()
        gold = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).scalar_one()
        gold_to_spend = 0
        res = []
        if blue_potions_num < 10 and gold >= 300:
            res.append(
                {
                    "sku": "MEDIUM_BLUE_BARREL",
                    "quantity": 1,
                }
            )
            gold_to_spend += 300
        elif blue_potions_num < 10 and gold >= 120:
            res.append(
                {
                    "sku": "SMALL_BLUE_BARREL",
                    "quantity": 1,
                }
            )
            gold_to_spend += 120
        if red_potions_num < 10 and (gold - gold_to_spend) >= 250:
            res.append(
                {
                    "sku": "MEDIUM_RED_BARREL",
                    "quantity": 1,
                }
            )
            gold_to_spend += 250
        elif red_potions_num < 10 and (gold - gold_to_spend) >= 100:
            res.append(
                {
                    "sku": "SMALL_RED_BARREL",
                    "quantity": 1,
                }
            )
            gold_to_spend += 100
        if green_potions_num < 10 and (gold - gold_to_spend) >= 100:
            res.append(
                {
                    "sku": "SMALL_GREEN_BARREL",
                    "quantity": 1,
                }
            )
        return res


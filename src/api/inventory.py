from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math
import sqlalchemy
from sqlalchemy import exc
from src import database as db

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.get("/audit")
def get_inventory():
    """ """
    with db.engine.begin() as connection:
        ml_gold_results = connection.execute(sqlalchemy.text('SELECT gold, num_green_ml, num_red_ml, num_blue_ml, num_dark_ml FROM global_inventory')).fetchone()
        gold, green_ml, red_ml, blue_ml, dark_ml = ml_gold_results
        # green_mL = connection.execute(sqlalchemy.text('SELECT num_green_ml FROM global_inventory')).scalar_one() 
        # red_mL = connection.execute(sqlalchemy.text('SELECT num_red_ml FROM global_inventory')).scalar_one()
        # blue_mL = connection.execute(sqlalchemy.text('SELECT num_blue_ml FROM global_inventory')).scalar_one()
        potion_total = connection.execute(sqlalchemy.text("SELECT SUM(quantity) AS total_potions FROM potions")).scalar()
        # green_potions = connection.execute(sqlalchemy.text('SELECT num_green_potions FROM global_inventory')).scalar_one()
        # red_potions = connection.execute(sqlalchemy.text('SELECT num_red_potions FROM global_inventory')).scalar_one()
        # blue_potions = connection.execute(sqlalchemy.text('SELECT num_blue_potions FROM global_inventory')).scalar_one()

    return {"number_of_potions": potion_total, "ml_in_barrels": green_ml + red_ml + blue_ml + dark_ml, "gold": gold}

# Gets called once a day
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """
    ml_cap = 0
    potion_cap = 0
    with db.engine.begin() as connection:
        gold = connection.execute(sqlalchemy.text('SELECT gold FROM global_inventory')).scalar_one()
        capacity_results = connection.execute(sqlalchemy.text('SELECT ml_capacity, potion_capacity FROM capacity')).fetchone()
        ml_cap, potion_cap = capacity_results
    if gold >= 12000 and ml_cap <= 10000 and potion_cap <= 50:
        return {
        "potion_capacity": 100,
        "ml_capacity": 20000
        }
    elif gold >= 6000 and ml_cap <= 20000 and potion_cap <= 100:
        return {
        "potion_capacity": 50,
        "ml_capacity": 10000
        }
    else:
        return {
            "potion_capacity": 0,
            "ml_capacity": 0
        }

class CapacityPurchase(BaseModel):
    potion_capacity: int
    ml_capacity: int

# Gets called once a day
@router.post("/deliver/{order_id}")
def deliver_capacity_plan(capacity_purchase : CapacityPurchase, order_id: int):
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """
    with db.engine.begin() as connection:
        try:
            connection.execute(sqlalchemy.text(
                "INSERT INTO processed (job_id, type) VALUES (:order_id, 'capacity')"
            ), {"order_id": order_id})
        except exc.IntegrityError as e:
            return "OK"
    potion_unit = capacity_purchase.potion_capacity // 50
    ml_unit = capacity_purchase.ml_capacity // 10000
    total_gold_spent = 1000 * (potion_unit + ml_unit)
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(f'UPDATE capacity SET potion_capacity = potion_capacity + :pot_cap'), {"pot_cap": capacity_purchase.potion_capacity})
        connection.execute(sqlalchemy.text(f'UPDATE capacity SET ml_capacity = ml_capacity + :ml'), {"ml": capacity_purchase.ml_capacity})
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET gold = gold - :gold_spent'), {"gold_spent": total_gold_spent})
    return "OK"

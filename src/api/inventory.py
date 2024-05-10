from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math
import sqlalchemy
from sqlalchemy import exc
from src import database as db

metadata_obj = sqlalchemy.MetaData()
transactions = sqlalchemy.Table("overall_transactions", metadata_obj, autoload_with=db.engine)
ml_ledger = sqlalchemy.Table("ml_ledger_entries", metadata_obj, autoload_with=db.engine)
gold_ledger = sqlalchemy.Table("gold_ledger_entries", metadata_obj, autoload_with=db.engine)

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.get("/audit")
def get_inventory():
    """ """
    with db.engine.begin() as connection:
        # ml_gold_results = connection.execute(sqlalchemy.text('SELECT gold, num_green_ml, num_red_ml, num_blue_ml, num_dark_ml FROM global_inventory')).fetchone()
        # gold, green_ml, red_ml, blue_ml, dark_ml = ml_gold_results
        gold = connection.execute(sqlalchemy.text("SELECT SUM(gold_change) FROM gold_ledger_entries")).scalar()
        ml = connection.execute(sqlalchemy.text("SELECT SUM(green_change), SUM(blue_change), SUM(red_change), SUM(dark_change) FROM ml_ledger_entries")).fetchone()
        green_ml, blue_ml, red_ml, dark_ml = ml
        total_ml = green_ml + blue_ml + red_ml + dark_ml
        #potion_total = connection.execute(sqlalchemy.text("SELECT SUM(quantity) AS total_potions FROM potions")).scalar()
        potion_total = connection.execute(sqlalchemy.text("SELECT SUM(quantity_change) FROM potions_ledger_entries")).scalar()
    return {"number_of_potions": potion_total, "ml_in_barrels": total_ml, "gold": gold}

# Gets called once a day around 1pm
@router.post("/plan")
def get_capacity_plan():
    """ 
    Start with 1 capacity for 50 potions and 1 capacity for 10000 ml of potion. Each additional 
    capacity unit costs 1000 gold.
    """
    ml_cap = 0
    potion_cap = 0
    with db.engine.begin() as connection:
        # gold = connection.execute(sqlalchemy.text('SELECT gold FROM global_inventory')).scalar_one()
        gold = connection.execute(sqlalchemy.text("SELECT SUM(gold_change) FROM gold_ledger_entries")).scalar()
        capacity_results = connection.execute(sqlalchemy.text('SELECT ml_capacity, potion_capacity FROM capacity')).fetchone()
        ml_cap, potion_cap = capacity_results
    if gold >= 9000:
        return {
        "potion_capacity": 2,
        "ml_capacity": 2
        }
    elif gold >= 2300:
        return {
        "potion_capacity": 1,
        "ml_capacity": 1
        }
    elif gold >= 1400:
        return {
        "potion_capacity": 1,
        "ml_capacity": 0
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
    potion_unit = capacity_purchase.potion_capacity 
    ml_unit = capacity_purchase.ml_capacity 
    total_gold_spent = 1000 * (potion_unit + ml_unit)
    with db.engine.begin() as connection:
        tx_id = connection.execute(sqlalchemy.text("INSERT INTO overall_transactions (description, type) VALUES ('Delivering capacity, order id :idd :potion potion units, :ml ml units', 'capacity deliver') RETURNING id"), {"idd": order_id, "potion": potion_unit, "ml": ml_unit}).scalar_one()
        connection.execute(sqlalchemy.text(f'UPDATE capacity SET potion_capacity = potion_capacity + :pot_cap'), {"pot_cap": capacity_purchase.potion_capacity * 50})
        connection.execute(sqlalchemy.text(f'UPDATE capacity SET ml_capacity = ml_capacity + :ml'), {"ml": capacity_purchase.ml_capacity * 10000})
        connection.execute(sqlalchemy.insert(gold_ledger), 
                           [
                               {"transaction_id": tx_id, "gold_change": total_gold_spent * -1}
                           ])
    return "OK"

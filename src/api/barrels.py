from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from sqlalchemy import exc
from src import database as db

metadata_obj = sqlalchemy.MetaData()
capacity = sqlalchemy.Table("capacity", metadata_obj, autoload_with=db.engine)
potions_inventory = sqlalchemy.Table("potions", metadata_obj, autoload_with=db.engine)
transactions = sqlalchemy.Table("overall_transactions", metadata_obj, autoload_with=db.engine)
ml_ledger = sqlalchemy.Table("ml_ledger_entries", metadata_obj, autoload_with=db.engine)
gold_ledger = sqlalchemy.Table("gold_ledger_entries", metadata_obj, autoload_with=db.engine)
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
    with db.engine.begin() as connection:
        try:
            connection.execute(sqlalchemy.text(
                "INSERT INTO processed (job_id, type) VALUES (:order_id, 'barrels')"
            ), {"order_id": order_id})
        except exc.IntegrityError as e:
            return "OK"
    total_green_ml = 0
    total_blue_ml = 0
    total_red_ml = 0
    total_price = 0
    total_dark_ml = 0
    for barrel in barrels_delivered:
        total_price += (barrel.price * barrel.quantity)
        if barrel.potion_type == [0, 1, 0, 0]:
            total_green_ml += (barrel.ml_per_barrel * barrel.quantity)
        elif barrel.potion_type == [1, 0, 0, 0]:
            total_red_ml += (barrel.ml_per_barrel * barrel.quantity)
        elif barrel.potion_type == [0, 0, 1, 0]:
            total_blue_ml += (barrel.ml_per_barrel * barrel.quantity)
        elif barrel.potion_type == [0, 0, 0, 1]:
            total_dark_ml += (barrel.ml_per_barrel * barrel.quantity)
        else:
            raise Exception("Invalid barrel potion type")
    with db.engine.begin() as connection:
        tx_id = connection.execute(sqlalchemy.text("INSERT INTO overall_transactions (description, type) VALUES ('Delivering barrels, order id :idd :red :green :blue :dark ', 'barrels deliver') RETURNING id"), {"idd": order_id, "red": total_red_ml, "green": total_green_ml, "blue": total_blue_ml, "dark": total_dark_ml}).scalar_one()
        # updating mL in ml ledger entries
        connection.execute(sqlalchemy.insert(ml_ledger), 
                           [
                               {"transaction_id": tx_id, "green_change": total_green_ml, "blue_change": total_blue_ml, "red_change": total_red_ml, "dark_change": total_dark_ml}
                           ])
        # updating gold in gold ledger entries
        connection.execute(sqlalchemy.insert(gold_ledger), 
                           [
                               {"transaction_id": tx_id, "gold_change": total_price * -1}
                           ])
        # connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_green_ml = num_green_ml + :total_green_ml'), [{"total_green_ml": total_green_ml}])
        # connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_red_ml = num_red_ml + :total_red_ml'), [{"total_red_ml": total_red_ml}])
        # connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_blue_ml = num_blue_ml + :total_blue_ml'), [{"total_blue_ml": total_blue_ml}])
        # connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_dark_ml = num_dark_ml + :total_dark_ml'), [{"total_dark_ml": total_dark_ml}])
        # # update gold left
        # connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET gold = gold - :total_price'), [{"total_price": total_price}])
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
        ml_capacity = connection.execute(sqlalchemy.text("SELECT ml_capacity FROM capacity")).scalar_one()
        gold = connection.execute(sqlalchemy.text("SELECT SUM(gold_change) FROM gold_ledger_entries")).scalar()
        # ml_gold = connection.execute(sqlalchemy.text("SELECT gold, num_green_ml, num_blue_ml, num_red_ml, num_dark_ml FROM global_inventory")).fetchone()
        ml = connection.execute(sqlalchemy.text("SELECT SUM(green_change), SUM(blue_change), SUM(red_change), SUM(dark_change) FROM ml_ledger_entries")).fetchone()
        green_ml, blue_ml, red_ml, dark_ml = ml
        total_ml = green_ml + blue_ml + red_ml + dark_ml
        print("Total ml: ", total_ml)
        dark_exist = False
        ml_per_color = (ml_capacity - dark_ml) / 3
        # Uncomment below once rich:
        # for barrel in wholesale_catalog:
        #     if barrel.potion_type == [0, 0, 0, 1] and (ml_capacity - total_ml >= 10000):
        #         ml_per_color = (ml_capacity - 10000) / 4
        #         dark_exist = True
        print("ml per color:", ml_per_color)
        print(f"green: {green_ml}, red: {red_ml}, blue: {blue_ml}, gold: {gold}, dark: {dark_ml}")
        gold_to_spend = 0
        res = []
        if dark_exist and (gold >= 1000) and dark_ml <= 0 and ((ml_capacity - total_ml) >= 10000) :
            res.append(
                 {
                    "sku": "LAGE_DARK_BARREL",
                    "quantity": 1
                }
            )
            gold_to_spend += 700
        if (gold - gold_to_spend) >= 250 and (green_ml <= (ml_per_color - 2500)):
            res.append(
                {
                    "sku": "MEDIUM_GREEN_BARREL",
                    "quantity": 1
                }
            )
            gold_to_spend += 250
        # elif (gold - gold_to_spend) >= 200 and (green_ml <= (ml_per_color - 1000)):
        #     res.append(
        #         {
        #             "sku": "SMALL_GREEN_BARREL",
        #             "quantity": 2
        #         }
        #     )
        #     gold_to_spend += 200
        # elif (gold - gold_to_spend) >= 100 and (green_ml <= (ml_per_color - 500)):
        #     res.append(
        #         {
        #             "sku": "SMALL_GREEN_BARREL",
        #             "quantity": 1
        #         }
        #     )
            # gold_to_spend += 100
        if ((gold - gold_to_spend) >= 300) and (blue_ml <= (ml_per_color - 2500)):
            res.append(
                {
                    "sku": "MEDIUM_BLUE_BARREL",
                    "quantity": 1
                }
            )
            gold_to_spend += 300
        # elif ((gold - gold_to_spend) >= 240) and (blue_ml <= (ml_per_color - 1000)):
        #     res.append(
        #         {
        #             "sku": "SMALL_BLUE_BARREL",
        #             "quantity": 2
        #         }
        #     )
        #     gold_to_spend += (120 * 2)
        # elif ((gold - gold_to_spend) >= 120) and (blue_ml <= (ml_per_color - 500)):
        #     res.append(
        #         {
        #             "sku": "SMALL_BLUE_BARREL",
        #             "quantity": 1
        #         }
        #     )
            # gold_to_spend += 120 
        if ((gold - gold_to_spend) - gold_to_spend) >= 250 and (red_ml <= (ml_per_color - 2500)):
            res.append(
                {
                    "sku": "MEDIUM_RED_BARREL",
                    "quantity": 1
                }
            )
            gold_to_spend += 250
        # elif (gold - gold_to_spend) >= 200 and (red_ml <= (ml_per_color - 1000)):
        #     res.append(
        #         {
        #             "sku": "SMALL_RED_BARREL",
        #             "quantity": 2
        #         }
        #     )
        #     gold_to_spend += 200
        # elif (gold - gold_to_spend) >= 100 and (red_ml <= (ml_per_color - 500)):
        #     res.append(
        #         {
        #             "sku": "SMALL_RED_BARREL",
        #             "quantity": 1
        #         }
        #     )
            # gold_to_spend += 100
        print("gold spent:", gold_to_spend)
        return res


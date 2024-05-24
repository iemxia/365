from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
import math
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
    print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")
    return "OK"

# Gets called once a day
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
        large_exist = False

        ml_per_color = 6500
        # Uncomment below once rich:
        for barrel in wholesale_catalog:
            if barrel.potion_type == [0, 0, 0, 1] and (ml_capacity - total_ml >= 10000):
                ml_per_color = ml_capacity / 3
                dark_exist = True
            if "LARGE" in barrel.sku:
                large_exist = True
        
        gold_to_spend = 0
        res = []
        # def calculate_barrels(ml_needed, barrel_capacity, ml_color, available_gold, barrel_price):
        #     max_barrels_capacity = max(0, (ml_needed - ml_color) // barrel_capacity)
        #     max_barrels_gold = available_gold // (barrel_price)
        #     return max(0, min(max_barrels_capacity, max_barrels_gold, 7))
        # if total_ml < 60000:
        #     if green_ml < ml_per_color:
        #         if large_exist:
        #             large_green_needed = calculate_barrels(ml_per_color, 10000, green_ml, gold - gold_to_spend, 400)
        #             if large_green_needed > 0:
        #                 res.append({"sku": "LARGE_GREEN_BARREL", "quantity": int(large_green_needed)})
        #                 gold_to_spend += large_green_needed * 400
        #                 green_ml += large_green_needed * 10000
        #         medium_green_needed = calculate_barrels(ml_per_color, 2500, green_ml, gold - gold_to_spend, 250)
        #         if medium_green_needed > 0:
        #             res.append({"sku": "MEDIUM_GREEN_BARREL", "quantity": int(medium_green_needed)})
        #             gold_to_spend += medium_green_needed * 250
        #             green_ml += medium_green_needed * 2500
        #     # Replenish blue mL
        #     if blue_ml < ml_per_color:
        #         if large_exist:
        #             large_blue_needed = calculate_barrels(ml_per_color, 10000, blue_ml, gold - gold_to_spend, 600)
        #             if large_blue_needed > 0:
        #                 res.append({"sku": "LARGE_BLUE_BARREL", "quantity": int(large_blue_needed)})
        #                 gold_to_spend += large_blue_needed * 600
        #                 blue_ml += large_blue_needed * 10000
        #         medium_blue_needed = calculate_barrels(ml_per_color, 2500, blue_ml, gold - gold_to_spend, 300)
        #         if medium_blue_needed > 0:
        #             res.append({"sku": "MEDIUM_BLUE_BARREL", "quantity": int(medium_blue_needed)})
        #             gold_to_spend += medium_blue_needed * 300
        #             blue_ml += medium_blue_needed * 2500
        #     # Replenish red mL
        #     if red_ml < ml_per_color:
        #         if large_exist:
        #             large_red_needed = calculate_barrels(ml_per_color, 10000, red_ml, gold - gold_to_spend, 500)
        #             if large_red_needed > 0:
        #                 res.append({"sku": "LARGE_RED_BARREL", "quantity": int(large_red_needed)})
        #                 gold_to_spend += large_red_needed * 500
        #                 red_ml += large_red_needed * 10000
        #         medium_red_needed = calculate_barrels(ml_per_color, 2500, red_ml, gold - gold_to_spend, 250)
        #         if medium_red_needed > 0:
        #             res.append({"sku": "MEDIUM_RED_BARREL", "quantity": int(medium_red_needed)})
        #             gold_to_spend += medium_red_needed * 250
        #             red_ml += medium_red_needed * 2500
        print("ml per color:", ml_per_color)
        print(f"new mL amount: green: {green_ml}, red: {red_ml}, blue: {blue_ml}, gold: {gold}, dark: {dark_ml}")
        print("new total:", green_ml + red_ml + blue_ml + dark_ml)
        print("Gold spent: ", gold_to_spend)
        return res
        # if large_exist and (gold - gold_to_spend) >= 400 and (green_ml <= (ml_per_color - 10000)):
        #     res.append(
        #         {
        #             "sku": "LARGE_GREEN_BARREL",
        #             "quantity": 1
        #         }
        #     )
        #     gold_to_spend += 400
        # elif (gold - gold_to_spend) >= 500 and (green_ml <= (ml_per_color - 5000)):
        #     res.append(
        #         {
        #             "sku": "MEDIUM_GREEN_BARREL",
        #             "quantity": 2
        #         }
        #     )
        #     gold_to_spend += 500
        # elif (gold - gold_to_spend) >= 250 and (green_ml <= (ml_per_color - 2500)):
        #     res.append(
        #         {
        #             "sku": "MEDIUM_GREEN_BARREL",
        #             "quantity": 1
        #         }
        #     )
        #     gold_to_spend += 250
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
        #     gold_to_spend += 100
        # if large_exist and (gold - gold_to_spend) >= 600 and (blue_ml <= (ml_per_color - 10000)):
        #     res.append(
        #         {
        #             "sku": "LARGE_BLUE_BARREL",
        #             "quantity": 1
        #         }
        #     )
        #     gold_to_spend += 600
        # elif ((gold - gold_to_spend) >= 600) and (blue_ml <= (ml_per_color - 5000)):
        #     res.append(
        #         {
        #             "sku": "MEDIUM_BLUE_BARREL",
        #             "quantity": 2
        #         }
        #     )
        #     gold_to_spend += 600
        # elif ((gold - gold_to_spend) >= 300) and (blue_ml <= (ml_per_color - 2500)):
        #     res.append(
        #         {
        #             "sku": "MEDIUM_BLUE_BARREL",
        #             "quantity": 1
        #         }
        #     )
        #     gold_to_spend += 300
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
        #     gold_to_spend += 120 
        # if large_exist and (gold - gold_to_spend) >= 500 and (red_ml <= (ml_per_color - 10000)):
        #     res.append(
        #         {
        #             "sku": "LARGE_RED_BARREL",
        #             "quantity": 1
        #         }
        #     )
        #     gold_to_spend += 500
        # elif (gold - gold_to_spend) >= 500 and (red_ml <= (ml_per_color - 5000)):
        #     res.append(
        #         {
        #             "sku": "MEDIUM_RED_BARREL",
        #             "quantity": 2
        #         }
        #     )
        #     gold_to_spend += 500
        # elif (gold - gold_to_spend) >= 250 and (red_ml <= (ml_per_color - 2500)):
        #     res.append(
        #         {
        #             "sku": "MEDIUM_RED_BARREL",
        #             "quantity": 1
        #         }
        #     )
        #     gold_to_spend += 250
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
        #     gold_to_spend += 100
        # def calculate_barrels(ml_needed, barrel_capacity, ml_color, available_gold, barrel_price):
        #     max_barrels_capacity = max(0, (ml_needed - ml_color) // barrel_capacity)
        #     max_barrels_gold = available_gold // (barrel_price)
        #     return max(0, min(max_barrels_capacity, max_barrels_gold, 4))
        
        # if dark_ml < ml_per_color:
        #     if large_exist and dark_exist:
        #         large_dark_needed = calculate_barrels(ml_per_color, 10000, dark_ml, gold - gold_to_spend, 700)
        #         if large_dark_needed > 0:
        #             res.append({"sku": "LARGE_DARK_BARREL", "quantity": int(large_dark_needed)})
        #             gold_to_spend += large_dark_needed * 700
        #             dark_ml += large_dark_needed * 10000
        # # replenish green ml
        # if green_ml < ml_per_color:
        #     if large_exist:
        #         large_green_needed = calculate_barrels(ml_per_color, 10000, green_ml, gold - gold_to_spend, 400)
        #         if large_green_needed > 0:
        #             res.append({"sku": "LARGE_GREEN_BARREL", "quantity": int(large_green_needed)})
        #             gold_to_spend += large_green_needed * 400
        #             green_ml += large_green_needed * 10000
        #     medium_green_needed = calculate_barrels(ml_per_color, 2500, green_ml, gold - gold_to_spend, 250)
        #     if medium_green_needed > 0:
        #         res.append({"sku": "MEDIUM_GREEN_BARREL", "quantity": int(medium_green_needed)})
        #         gold_to_spend += medium_green_needed * 250
        #         green_ml += medium_green_needed * 2500
        #     small_green_needed = calculate_barrels(ml_per_color, 500, green_ml, gold - gold_to_spend, 100)
        #     if small_green_needed > 0:
        #         res.append({"sku": "SMALL_GREEN_BARREL", "quantity": int(small_green_needed)})
        #         gold_to_spend += small_green_needed * 100
        #         green_ml += small_green_needed * 500

        # # Replenish blue mL
        # if blue_ml < ml_per_color:
        #     if large_exist:
        #         large_blue_needed = calculate_barrels(ml_per_color, 10000, blue_ml, gold - gold_to_spend, 600)
        #         if large_blue_needed > 0:
        #             res.append({"sku": "LARGE_BLUE_BARREL", "quantity": int(large_blue_needed)})
        #             gold_to_spend += large_blue_needed * 600
        #             blue_ml += large_blue_needed * 10000
        #     medium_blue_needed = calculate_barrels(ml_per_color, 2500, blue_ml, gold - gold_to_spend, 300)
        #     if medium_blue_needed > 0:
        #         res.append({"sku": "MEDIUM_BLUE_BARREL", "quantity": int(medium_blue_needed)})
        #         gold_to_spend += medium_blue_needed * 300
        #         blue_ml += medium_blue_needed * 2500
        #     small_blue_needed = calculate_barrels(ml_per_color, 500, blue_ml, gold - gold_to_spend, 120)
        #     if small_blue_needed > 0:
        #         res.append({"sku": "SMALL_BLUE_BARREL", "quantity": int(small_blue_needed)})
        #         gold_to_spend += small_blue_needed * 120
        #         blue_ml += small_blue_needed * 500
        
        # # Replenish red mL
        # if red_ml < ml_per_color:
        #     if large_exist:
        #         large_red_needed = calculate_barrels(ml_per_color, 10000, red_ml, gold - gold_to_spend, 500)
        #         if large_red_needed > 0:
        #             res.append({"sku": "LARGE_RED_BARREL", "quantity": int(large_red_needed)})
        #             gold_to_spend += large_red_needed * 500
        #             red_ml += large_red_needed * 10000
        #     medium_red_needed = calculate_barrels(ml_per_color, 2500, red_ml, gold - gold_to_spend, 250)
        #     if medium_red_needed > 0:
        #         res.append({"sku": "MEDIUM_RED_BARREL", "quantity": int(medium_red_needed)})
        #         gold_to_spend += medium_red_needed * 250
        #         red_ml += medium_red_needed * 2500
        #     small_red_needed = calculate_barrels(ml_per_color, 500, red_ml, gold - gold_to_spend, 100)
        #     if small_red_needed > 0:
        #         res.append({"sku": "SMALL_RED_BARREL", "quantity": int(small_red_needed)})
        #         gold_to_spend += small_red_needed * 100
        #         red_ml += small_red_needed * 500
        

# Reuse this once I am past a certain time and don't wanna buy bunch of mL anymore
 

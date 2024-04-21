from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

metadata_obj = sqlalchemy.MetaData()
capacity = sqlalchemy.Table("capacity", metadata_obj, autoload_with=db.engine)
global_inventory = sqlalchemy.Table("global_inventory", metadata_obj, autoload_with=db.engine)
potions_inventory = sqlalchemy.Table("potions", metadata_obj, autoload_with=db.engine)
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
        # update mL of green
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_green_ml = num_green_ml + :total_green_ml'), [{"total_green_ml": total_green_ml}])
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_red_ml = num_red_ml + :total_red_ml'), [{"total_red_ml": total_red_ml}])
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_blue_ml = num_blue_ml + :total_blue_ml'), [{"total_blue_ml": total_blue_ml}])
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_dark_ml = num_dark_ml + :total_dark_ml'), [{"total_dark_ml": total_dark_ml}])
        # update gold left
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET gold = gold - :total_price'), [{"total_price": total_price}])
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
        #cap_row = connection.execute(sqlalchemy.text("SELECT :ml_capacity, :potion_capacity, :units FROM capacity"), [{"ml_capacity": "ml_capacity", "potion_capacity": "potion_capacity", "units": "units"}]).one()
        #cap_row = connection.execute(sqlalchemy.text("SELECT ml_capacity, potion_capacity, units FROM capacity")).one()
        ml_capacity = connection.execute(sqlalchemy.text("SELECT ml_capacity FROM capacity")).scalar_one()
        # for id, ml_cap, potion_cap, units in cap_result:
        #     print(f"ml capacity: {ml_cap * units}, potion_cap: {potion_cap * units}, units: {units}")
        #     ml_capacity = ml_cap * units
        for barrel in wholesale_catalog:
            if barrel.potion_type == [0, 0, 0, 1]:
                ml_per_color = ml_capacity / 4
            else:
                ml_per_color = ml_capacity / 3
        print("ml per color:", ml_per_color)
        # green_potion = connection.execute(sqlalchemy.select(potions_inventory).where(potions_inventory.c.name ))
        green_ml= connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory")).scalar_one()
        blue_ml = connection.execute(sqlalchemy.text("SELECT num_blue_ml FROM global_inventory")).scalar_one()
        red_ml = connection.execute(sqlalchemy.text("SELECT num_red_ml FROM global_inventory")).scalar_one()
        dark_ml = connection.execute(sqlalchemy.text("SELECT num_dark_ml FROM global_inventory")).scalar_one()
        gold = connection.execute(sqlalchemy.text("SELECT gold FROM global_inventory")).scalar_one()
        print(f"green: {green_ml}, red: {red_ml}, blue: {blue_ml}, gold: {gold}, dark: {dark_ml}")
        gold_to_spend = 0
        res = []
        if (gold >= 300) and blue_ml <= (ml_per_color - 2500):
            res.append(
                {
                    "sku": "MEDIUM_BLUE_BARREL",
                    "quantity": 1,
                }
            )
            gold_to_spend += 300
        elif (gold >= 240) and (blue_ml <= (ml_per_color - 1000)):
            res.append(
                {
                    "sku": "SMALL_BLUE_BARREL",
                    "quantity": 2,
                }
            )
            gold_to_spend += (120 * 2)
        elif (gold >= 120) and (blue_ml <= (ml_per_color - 500)):
            res.append(
                {
                    "sku": "SMALL_BLUE_BARREL",
                    "quantity": 1,
                }
            )
            gold_to_spend += 120 
        if (gold - gold_to_spend) >= 250 and (red_ml <= (ml_per_color - 2500)):
            res.append(
                {
                    "sku": "MEDIUM_RED_BARREL",
                    "quantity": 1,
                }
            )
            gold_to_spend += 250
        elif (gold - gold_to_spend) >= 200 and (red_ml <= (ml_per_color - 1000)):
            res.append(
                {
                    "sku": "SMALL_RED_BARREL",
                    "quantity": 2,
                }
            )
            gold_to_spend += 200
        elif (gold - gold_to_spend) >= 100 and (red_ml <= (ml_per_color - 500)):
            res.append(
                {
                    "sku": "SMALL_RED_BARREL",
                    "quantity": 1,
                }
            )
            gold_to_spend += 100
        if (gold - gold_to_spend) >= 250 and (green_ml <= (ml_per_color - 2500)):
            res.append(
                {
                    "sku": "MEDIUM_GREEN_BARREL",
                    "quantity": 1,
                }
            )
            gold_to_spend += 250
        elif (gold - gold_to_spend) >= 200 and (green_ml <= (ml_per_color - 1000)):
            res.append(
                {
                    "sku": "SMALL_GREEN_BARREL",
                    "quantity": 2,
                }
            )
            gold_to_spend += 200
        elif (gold - gold_to_spend) >= 100 and (green_ml <= (ml_per_color - 500)):
            res.append(
                {
                    "sku": "SMALL_GREEN_BARREL",
                    "quantity": 1,
                }
            )
            gold_to_spend += 100
        print("gold spent:", gold_to_spend)
        return res


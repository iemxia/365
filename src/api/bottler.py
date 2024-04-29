from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from sqlalchemy import exc
from src import database as db

metadata_obj = sqlalchemy.MetaData()
capacity = sqlalchemy.Table("capacity", metadata_obj, autoload_with=db.engine)
global_inventory = sqlalchemy.Table("global_inventory", metadata_obj, autoload_with=db.engine)
potions_inventory = sqlalchemy.Table("potions", metadata_obj, autoload_with=db.engine)
transactions = sqlalchemy.Table("overall_transactions", metadata_obj, autoload_with=db.engine)
ml_ledger = sqlalchemy.Table("ml_ledger_entries", metadata_obj, autoload_with=db.engine)
potion_ledger = sqlalchemy.Table("potions_ledger_entries", metadata_obj, autoload_with=db.engine)
router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    """ """
    with db.engine.begin() as connection:
        try:
            connection.execute(sqlalchemy.text(
                "INSERT INTO processed (job_id, type) VALUES (:order_id, 'potions')"
            ), {"order_id": order_id})
        except exc.IntegrityError as e:
            return "OK"
    #[r, g, b, d]
    total_ml_subtract = [0, 0, 0, 0]
    with db.engine.begin() as connection:
        # for potion in potions_delivered:
        #     ml_values = [0, 0, 0, 0]
        #     for i, potion_type in enumerate(potion.potion_type):
        #         if potion_type > 0:
        #             ml_values[i] = potion_type
        #             total_ml_subtract[i] += ml_values[i] * potion.quantity
        #             connection.execute(sqlalchemy.text("UPDATE potions SET quantity = quantity + :num WHERE (green_ml = :green AND red_ml = :red AND blue_ml = :blue AND dark_ml = :dark )"), {"num": potion.quantity, "green": ml_values[1], "red": ml_values[0], "blue": ml_values[2], "dark": ml_values[3]})
        # connection.execute(sqlalchemy.text("UPDATE global_inventory SET num_red_ml = num_red_ml - :red, num_green_ml = num_green_ml - :green, num_blue_ml = num_blue_ml - :blue, num_dark_ml = num_dark_ml - :dark"), {"green": total_ml_subtract[1], "red": total_ml_subtract[0], "blue": total_ml_subtract[2], "dark": total_ml_subtract[3]})
        tx_id = connection.execute(sqlalchemy.text("INSERT INTO overall_transactions (description, type) VALUES ('Delivering potions, order id :idd ', 'bottler deliver') RETURNING id"), {"idd": order_id}).scalar_one()
        for potion in potions_delivered:
            for i in range(4):
                # get the total number of mL i will need to subtract 
                total_ml_subtract[i] -= potion.potion_type[i] * potion.quantity
            potion_id = connection.execute(sqlalchemy.text("SELECT id FROM potions WHERE :type = potion_type "), {"type": potion.potion_type}).scalar_one()
            connection.execute(sqlalchemy.insert(potion_ledger), 
                           [
                               {"transaction_id": tx_id, "potion_id": potion_id, "quantity_change": potion.quantity}
                           ])
        connection.execute(sqlalchemy.insert(ml_ledger), 
                           [
                               {"transaction_id": tx_id, "green_change": total_ml_subtract[1], "blue_change": total_ml_subtract[2], "red_change": total_ml_subtract[0], "dark_change": total_ml_subtract[3]}
                           ])
    print(f"potions delievered: {potions_delivered} order_id: {order_id}")

    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    # Initial logic: bottle all barrels into red potions.
    
    with db.engine.begin() as connection:
        # ml = connection.execute(sqlalchemy.text("SELECT num_green_ml, num_blue_ml, num_red_ml, num_dark_ml FROM global_inventory")).fetchone()
        ml = connection.execute(sqlalchemy.text("SELECT SUM(green_change), SUM(blue_change), SUM(red_change), SUM(dark_change) FROM ml_ledger_entries")).fetchone()
        if ml is None:
            ml = 0
        green_ml, blue_ml, red_ml, dark_ml = ml
        potion_capacity = connection.execute(sqlalchemy.text("SELECT potion_capacity FROM capacity")).scalar_one()
        # total_potions = connection.execute(sqlalchemy.text("SELECT SUM(quantity) AS total_potions FROM potions")).scalar()
        total_potions = connection.execute(sqlalchemy.text("SELECT SUM(quantity_change) FROM potions_ledger_entries")).scalar_one()
        if total_potions == None:
            total_potions = 0
        print("total potions owned: ", total_potions)
        available_to_make = potion_capacity - total_potions
        if dark_ml >= 100:
            potion_per_color = available_to_make // 6
            absolute_max = potion_capacity // 6
        else:
            potion_per_color = available_to_make // 5
            absolute_max = potion_capacity // 5
        print("potions per color: ", potion_per_color)
        res = []
        #[r, g, b, d]
        # Make custom ones first?
        potion_res = {}
        num_potions = {}
        # potions = connection.execute(sqlalchemy.text("SELECT potion_sku, red_ml, green_ml, blue_ml, dark_ml FROM potions"))
        potions = connection.execute(sqlalchemy.text("SELECT potion_sku, potion_type, id FROM potions"))
        magenta = connection.execute(sqlalchemy.text("SELECT potion_type FROM potions WHERE potion_sku = 'astral_magenta' ")).scalar_one()
        trix = connection.execute(sqlalchemy.text("SELECT potion_type FROM potions WHERE potion_sku = 'trix_are_for_kids' ")).scalar_one()
        for row in potions:
            sku, potion_type, id = row
            potion_res[sku] = potion_type
            num_potions[id] = connection.execute(sqlalchemy.text("SELECT SUM(quantity_change) FROM potions_ledger_entries WHERE potion_id = :pot_id "), {"pot_id": id}).scalar_one()
        print(num_potions)
        purple_to_make = 0
        while (red_ml >= magenta[0]) and (blue_ml >= magenta[2]) and (purple_to_make < potion_per_color and (num_potions[4] < absolute_max)):
            purple_to_make += 1
            red_ml -= magenta[0]
            blue_ml -= magenta[2]
        rgb_to_make = 0
        while (red_ml >= trix[0]) and (blue_ml >= trix[2]) and (green_ml >= trix[1]) and (rgb_to_make < potion_per_color) and (num_potions[5] < absolute_max):
            rgb_to_make += 1
            red_ml -= trix[0]
            blue_ml -= trix[2]
            green_ml -= trix[1]
        if (num_potions[0] < absolute_max):
            if green_ml >= (100 * potion_per_color):
                res.append(
                        {
                            "potion_type": potion_res["mosh_pit"],
                            "quantity": potion_per_color,
                        })
                green_ml -= (100 * potion_per_color)
            elif green_ml >= 100:
                res.append(
                        {
                            "potion_type": potion_res["mosh_pit"],
                            "quantity": green_ml // 100
                        })
                green_ml -= (100 * (green_ml // 100))  
        if (num_potions[2] < absolute_max):
            if red_ml >= (100 * potion_per_color):
                print("red appending to list")
                res.append(
                        {
                            "potion_type": potion_res["thrash_red"],
                            "quantity": potion_per_color
                        })
                red_ml -= (100 * potion_per_color)
            elif red_ml >= 100:
                res.append(
                    {
                        "potion_type": potion_res["thrash_red"],
                        "quantity": red_ml // 100
                    }
                )
                red_ml -= (100 * (red_ml // 100))
        if (num_potions[1] < absolute_max):
            if blue_ml >= (100 * potion_per_color):
                res.append(
                        {
                            "potion_type": potion_res["dizzy_blue"],
                            "quantity": potion_per_color
                        })
                blue_ml -= (100 * potion_per_color)
            elif blue_ml >= 100:
                res.append(
                    {
                        "potion_type": potion_res["dizzy_blue"],
                        "quantity": blue_ml // 100
                    }
                )
                blue_ml -= (100 * (blue_ml // 100))
        if (num_potions[4] < absolute_max):
            if dark_ml >= (100 * potion_per_color):
                res.append(
                        {
                            "potion_type": potion_res["fade_dark"],
                            "quantity": potion_per_color
                        })
                dark_ml -= (100 * potion_per_color)
        if (num_potions[3] < absolute_max):
            if purple_to_make > 0:
                res.append({
                            "potion_type": potion_res["astral_magenta"],
                            "quantity": purple_to_make
                        })
        if (num_potions[5] < absolute_max):
            if rgb_to_make > 0:
                res.append({
                            "potion_type": potion_res["trix_are_for_kids"],
                            "quantity": rgb_to_make
                        })
    return res

if __name__ == "__main__":
    print(get_bottle_plan())
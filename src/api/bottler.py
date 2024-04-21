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
    red = 0
    blue = 0
    green = 0
    dark = 0
    purple = 0
    rgb_mix = 0
    ml_green = 0
    ml_red = 0
    ml_blue = 0
    ml_dark = 0
    #[r, g, b, d]
    # need to also subtract mL from inventory (100 mL per potion)
    for potion in potions_delivered:
        if potion.potion_type[0] == 100:
            red += potion.quantity
            ml_red += (potion.potion_type[0] * potion.quantity)
        elif potion.potion_type[1] == 100:
            green += potion.quantity
            ml_green += (potion.potion_type[1] * potion.quantity)
        elif potion.potion_type[2] == 100:
            blue += potion.quantity
            ml_blue += (potion.potion_type[2] * potion.quantity)
        elif potion.potion_type[3] == 100:
            dark += potion.quantity
            ml_dark += (potion.potion_type[3] * potion.quantity)
        elif potion.potion_type == [50, 0, 50, 0]:
            ml_red += (50 * potion.quantity)
            ml_blue += (50 * potion.quantity)
            purple += potion.quantity
        elif potion.potion_type == [33, 33, 34, 0]:
            ml_red += (33 * potion.quantity)
            ml_green += (33 * potion.quantity)
            ml_blue += (34 * potion.quantity)
            rgb_mix += potion.quantity
        else:
            raise Exception("Invalid Potion Type")
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(f'UPDATE potions SET quantity = quantity + :green WHERE green_ml = 100'), {"green": green})
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_green_ml = num_green_ml - :ml_green'), {"ml_green": ml_green})
        connection.execute(sqlalchemy.text(f'UPDATE potions SET quantity = quantity + :red WHERE red_ml = 100'), {"red": red})
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_red_ml = num_red_ml - :ml_red'), {"ml_red": ml_red})
        connection.execute(sqlalchemy.text(f'UPDATE potions SET quantity = quantity + :blue WHERE blue_ml = 100'), {"blue": blue})
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_blue_ml = num_blue_ml - :ml_blue'), {"ml_blue": ml_blue})
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_dark_ml = num_dark_ml - :ml_dark'), {"ml_dark": ml_dark})
        connection.execute(sqlalchemy.text(f'UPDATE potions SET quantity = quantity + :purple WHERE blue_ml = 50 AND red_ml = 50'), {"purple": purple})
        connection.execute(sqlalchemy.text(f'UPDATE potions SET quantity = quantity + :rgb WHERE blue_ml = 34 AND red_ml = 33'), {"rgb": rgb_mix})
        connection.execute(sqlalchemy.text(f'UPDATE potions SET quantity = quantity + :dark WHERE dark_ml = 100'), {"dark": dark})
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
        ml = connection.execute(sqlalchemy.text("SELECT num_green_ml, num_blue_ml, num_red_ml, num_dark_ml FROM global_inventory")).fetchone()
        green_ml, blue_ml, red_ml, dark_ml = ml
        potion_capacity = connection.execute(sqlalchemy.text("SELECT potion_capacity FROM capacity")).scalar_one()
        print("red ml: ", red_ml)
        total_potions = connection.execute(sqlalchemy.text("SELECT SUM(quantity) AS total_potions FROM potions")).scalar()
        print("total potions owned: ", total_potions)
        available_to_make = potion_capacity - total_potions
        if dark_ml >= 100:
            potion_per_color = available_to_make // 6
        else:
            potion_per_color = available_to_make // 5
        print("potions per color: ", potion_per_color)
        res = []
        #[r, g, b, d]
        # Make custom ones first?
        purple_to_make = 0
        while (red_ml >= 50) and (blue_ml >= 50) and (purple_to_make <= potion_per_color):
            purple_to_make += 1
            red_ml -= 50
            blue_ml -= 50
        rgb_to_make = 0
        while (red_ml >= 33) and (blue_ml >= 34) and (green_ml >= 33) and (rgb_to_make <= potion_per_color):
            rgb_to_make += 1
            red_ml -= 33
            blue_ml -= 34
            green_ml -=33
        potion_res = {}
        potions = connection.execute(sqlalchemy.text("SELECT potion_sku, red_ml, green_ml, blue_ml, dark_ml FROM potions"))
        for row in potions:
            potion_sku, red, green, blue, dark = row
            potion_res[potion_sku] = [red, green, blue, dark]
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
        print("red ml: ", red_ml)    
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
        if dark_ml >= (100 * potion_per_color):
            res.append(
                    {
                        "potion_type": potion_res["fade_dark"],
                        "quantity": potion_per_color
                    })
            dark_ml -= (100 * potion_per_color)
        if purple_to_make > 0:
            res.append({
                        "potion_type": potion_res["astral_magenta"],
                        "quantity": purple_to_make
                    })
        if rgb_to_make > 0:
            res.append({
                        "potion_type": potion_res["trix_are_for_kids"],
                        "quantity": rgb_to_make
                    })
    return res

if __name__ == "__main__":
    print(get_bottle_plan())
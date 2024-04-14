from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

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
    red = 0
    blue = 0
    green = 0
    ml_green = 0
    ml_red = 0
    ml_blue = 0
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
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_green_potions = num_green_potions + {green}'))
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_green_ml = num_green_ml - {ml_green}'))
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_red_potions = num_red_potions + {red}'))
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_red_ml = num_red_ml - {ml_red}'))
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_blue_potions = num_blue_potions + {blue}'))
        connection.execute(sqlalchemy.text(f'UPDATE global_inventory SET num_blue_ml = num_blue_ml - {ml_blue}'))
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
        green_ml = connection.execute(sqlalchemy.text("SELECT num_green_ml FROM global_inventory")).scalar_one()
        red_ml = connection.execute(sqlalchemy.text("SELECT num_red_ml FROM global_inventory")).scalar_one()
        blue_ml = connection.execute(sqlalchemy.text("SELECT num_blue_ml FROM global_inventory")).scalar_one()
        green_potions_num = connection.execute(sqlalchemy.text("SELECT num_green_potions FROM global_inventory")).scalar_one()
        blue_potions_num = connection.execute(sqlalchemy.text("SELECT num_blue_potions FROM global_inventory")).scalar_one()
        red_potions_num = connection.execute(sqlalchemy.text("SELECT num_red_potions FROM global_inventory")).scalar_one()
        total_potions = green_potions_num + blue_potions_num + red_potions_num
        available_to_make = 50 - total_potions
        potion_per_color = available_to_make // 3
        res = []
        
        #[r, g, b, d]
        if green_ml >= 500:
            res.append(
                    {
                        "potion_type": [0, 100, 0, 0],
                        "quantity": 5,
                    })
        if red_ml >= (100 * potion_per_color):
            res.append(
                    {
                        "potion_type": [100, 0, 0, 0],
                        "quantity": potion_per_color
                    })
        elif red_ml >= 500:
            res.append(
                    {
                        "potion_type": [100, 0, 0, 0],
                        "quantity": 5
                    })
        if blue_ml >= (100 * potion_per_color):
            res.append(
                    {
                        "potion_type": [0, 0, 100, 0],
                        "quantity": potion_per_color
                    })
        elif blue_ml >= 500:
            res.append(
                    {
                        "potion_type": [0, 0, 100, 0],
                        "quantity": 5
                    })
    return res

if __name__ == "__main__":
    print(get_bottle_plan())
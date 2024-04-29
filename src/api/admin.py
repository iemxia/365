from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/reset")
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from
    inventory, and all barrels are removed from inventory. Carts are all reset.
    """
    with db.engine.begin() as connection:
        connection.execute(sqlalchemy.text("TRUNCATE TABLE carts CASCADE"))
        connection.execute(sqlalchemy.text("TRUNCATE TABLE overall_transactions CASCADE"))
        # connection.execute(sqlalchemy.text("TRUNCATE TABLE cart_items CASCADE"))
        # connection.execute(sqlalchemy.text("TRUNCATE TABLE gold_ledger_entries"))
        # connection.execute(sqlalchemy.text("TRUNCATE TABLE ml_ledger_entries"))
        # connection.execute(sqlalchemy.text("TRUNCATE TABLE potions_ledger_entries"))
        connection.execute(sqlalchemy.text("INSERT INTO gold_ledger_entries (gold_change) VALUES (100)"))
        connection.execute(sqlalchemy.text("INSERT INTO ml_ledger_entries (id) VALUES (0)"))
        connection.execute(sqlalchemy.text("UPDATE capacity SET potion_capacity = 50, ml_capacity = 10000"))

    return "OK"


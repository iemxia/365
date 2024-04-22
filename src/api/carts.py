from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
from sqlalchemy import exc
import sqlalchemy
from src import database as db
metadata_obj = sqlalchemy.MetaData()
capacity = sqlalchemy.Table("capacity", metadata_obj, autoload_with=db.engine)
global_inventory = sqlalchemy.Table("global_inventory", metadata_obj, autoload_with=db.engine)
potions_inventory = sqlalchemy.Table("potions", metadata_obj, autoload_with=db.engine)
carts = sqlalchemy.Table("carts", metadata_obj, autoload_with=db.engine)
cart_items = sqlalchemy.Table("cart_items", metadata_obj, autoload_with=db.engine)

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)


class search_sort_options(str, Enum):
    customer_name = "customer_name"
    item_sku = "item_sku"
    line_item_total = "line_item_total"
    timestamp = "timestamp"


class search_sort_order(str, Enum):
    asc = "asc"
    desc = "desc"   


@router.get("/search/", tags=["search"])
def search_orders(
    customer_name: str = "",
    potion_sku: str = "",
    search_page: str = "",
    sort_col: search_sort_options = search_sort_options.timestamp,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Search for cart line items by customer name and/or potion sku.

    Customer name and potion sku filter to orders that contain the 
    string (case insensitive). If the filters aren't provided, no
    filtering occurs on the respective search term.

    Search page is a cursor for pagination. The response to this
    search endpoint will return previous or next if there is a
    previous or next page of results available. The token passed
    in that search response can be passed in the next search request
    as search page to get that page of results.

    Sort col is which column to sort by and sort order is the direction
    of the search. They default to searching by timestamp of the order
    in descending order.

    The response itself contains a previous and next page token (if
    such pages exist) and the results as an array of line items. Each
    line item contains the line item id (must be unique), item sku, 
    customer name, line item total (in gold), and timestamp of the order.
    Your results must be paginated, the max results you can return at any
    time is 5 total line items.
    """

    return {
        "previous": "",
        "next": "",
        "results": [
            {
                "line_item_id": 1,
                "item_sku": "1 oblivion potion",
                "customer_name": "Scaramouche",
                "line_item_total": 50,
                "timestamp": "2021-01-01T00:00:00Z",
            }
        ],
    }


class Customer(BaseModel):
    customer_name: str
    character_class: str
    level: int


# log the visit and customer list
@router.post("/visits/{visit_id}")
def post_visits(visit_id: int, customers: list[Customer]):
    """
    Which customers visited the shop today?
    """
    print(customers)

    return "OK"


@router.post("/")
def create_cart(new_cart: Customer):
    """ """
    with db.engine.begin() as connection:
        cart_id = connection.execute(sqlalchemy.text("INSERT INTO carts (customer_class) VALUES (:class) RETURNING cart_id"), {"class": new_cart.character_class}).scalar_one()
    return {"cart_id": cart_id}


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    quantity = cart_item.quantity
    with db.engine.begin() as connection:
        potion_id = connection.execute(sqlalchemy.text("SELECT id FROM potions WHERE potion_sku = :sku"), {"sku": item_sku}).scalar_one()
        potion_inventory = connection.execute(sqlalchemy.text("SELECT quantity FROM potions WHERE potion_sku = :sku"), {"sku": item_sku}).scalar_one()
        try:   # try to update the catalog so that customers don't try to buy at the same time and then I don't have enough?
            connection.execute(sqlalchemy.text("UPDATE catalog SET quantity = quantity - :q WHERE id = :id"), {"q": quantity, "id": potion_id})
        except exc.IntegrityError as e:
            raise Exception(f"Cannot add to cart, in inventory: {potion_inventory}, trying to buy: {quantity}")
        print(f"cart_id: {cart_id}, potion sku: {item_sku}, quantity: {quantity}")
        potion_cost = connection.execute(sqlalchemy.text("SELECT price FROM potions WHERE potion_sku = :sku"), {"sku": item_sku}).scalar_one()
        connection.execute(sqlalchemy.text("UPDATE carts SET total_potions_bought = total_potions_bought + :potions_bought, total_cost = total_cost + :cost WHERE cart_id = :id"), {"potions_bought": quantity, "cost": potion_cost * quantity, "id": cart_id})
        connection.execute(
        sqlalchemy.insert(cart_items),
            [
                {"cart_id": cart_id, "potion_id": potion_id, "quantity": quantity, "gold_cost": potion_cost * quantity}
            ]
        )
    return "OK"

# new branch, accidentally uploaded my postgres uri to public lol

class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    with db.engine.begin() as connection:
        # update gold
        total_cost = connection.execute(sqlalchemy.text("SELECT total_cost FROM carts WHERE cart_id = :id"), {"id": cart_id}).scalar_one()
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = gold + :total"), {"total": total_cost})
        # get total num of potions bought
        total_potions_bought = connection.execute(sqlalchemy.text("SELECT total_potions_bought FROM carts WHERE cart_id = :id"), {"id": cart_id}).scalar_one()
        # connection.execute(sqlalchemy.text("UPDATE carts SET total_potions_bought = :potions_bought, total_cost = :cost"), {"potions_bought": total_potions_bought, "cost": total_cost})
        # get all the items in the cart
        potions = connection.execute(sqlalchemy.text("SELECT potion_id, quantity FROM cart_items WHERE cart_id = :id"), {"id": cart_id}).fetchall()
        for potion_id, quantity in potions:
            # update the potion inventory for all the items they got
            connection.execute(sqlalchemy.text(f"UPDATE potions SET quantity = quantity - :potion_num WHERE id = :id"), {"potion_num": quantity, "id": potion_id})

    return {"total_potions_bought": total_potions_bought, "total_gold_paid": total_cost}

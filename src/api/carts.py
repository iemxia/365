from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
import sqlalchemy
from src import database as db

class MyCustomer:
    def __init__(self, name, potions, gold_paid):
        self.name = name
        self.potions  = potions
        self.gold_paid = gold_paid
    def __str__(self):
        return f"Name: {self.name}, Potions: {self.potions}, Gold Paid: {self.gold_paid}"

cart_id = 0

cart_dic = {}

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
    global cart_id
    cart_id += 1
    cart_dic[cart_id] = MyCustomer(new_cart.customer_name, [0, 0, 0, 0], 0)
    return {"cart_id": cart_id}


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    quantity = cart_item.quantity
    potions = cart_dic[cart_id].potions
    gold_paid = cart_dic[cart_id].gold_paid
     #[r, g, b, d]
    if "BLUE" in item_sku:
        print("blue potion now in cart")
        potions[2] += quantity
    if "RED" in item_sku:
        print("red potion now in cart")
        potions[0] += quantity
    if "GREEN" in item_sku:
        print("red potion now in cart")
        potions[1] += quantity
    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    cart = cart_dic[cart_id]
    print(cart)
    red = cart.potions[0]
    green = cart.potions[1]
    blue = cart.potions[2]
    prices = [45, 50, 65]  # red, green, blue
    gold_gained = (red * prices[0]) + (green * prices[1]) + (blue * prices[2])
    print("gold gained: ", gold_gained)
 
    with db.engine.begin() as connection:
        # update number of green potions, and make sure it doesn't go below 0
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_green_potions = num_green_potions - {green}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_red_potions = num_red_potions - {red}"))
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET num_blue_potions = num_blue_potions - {blue}"))
        # update gold
        connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = gold + {gold_gained}"))
    return {"total_potions_bought": 1, "total_gold_paid": gold_gained}

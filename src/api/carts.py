from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
from sqlalchemy import exc
import sqlalchemy
from src import database as db
import uuid
metadata_obj = sqlalchemy.MetaData()
capacity = sqlalchemy.Table("capacity", metadata_obj, autoload_with=db.engine)
potions_inventory = sqlalchemy.Table("potions", metadata_obj, autoload_with=db.engine)
carts = sqlalchemy.Table("carts", metadata_obj, autoload_with=db.engine)
cart_items = sqlalchemy.Table("cart_items", metadata_obj, autoload_with=db.engine)
transactions = sqlalchemy.Table("overall_transactions", metadata_obj, autoload_with=db.engine)
ml_ledger = sqlalchemy.Table("ml_ledger_entries", metadata_obj, autoload_with=db.engine)
gold_ledger = sqlalchemy.Table("gold_ledger_entries", metadata_obj, autoload_with=db.engine)
potion_ledger = sqlalchemy.Table("potions_ledger_entries", metadata_obj, autoload_with=db.engine)

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
    query = (
            sqlalchemy.select(
                carts.c.customer_name,
                potions_inventory.c.potion_sku,
                carts.c.total_potions_bought,
                carts.c.total_cost,
                carts.c.timestamp
            ).select_from(cart_items
                          .join(carts)
                          .join(potions_inventory, potions_inventory.c.id == cart_items.c.potion_id))
        )
    with db.engine.begin() as connection:
        if customer_name:
            query = query.where(carts.c.customer_name.ilike(f"{customer_name}"))
        if potion_sku:
            query = query.where(potions_inventory.c.potion_sku.ilike(f"{potion_sku}"))

        if sort_col is search_sort_options.customer_name:
            order_by = carts.c.customer_name
        elif sort_col is search_sort_options.item_sku:
            order_by = potions_inventory.c.potion_sku
        elif sort_col is search_sort_options.line_item_total:
            order_by = carts.c.total_cost
        else:
            order_by = carts.c.timestamp
        if sort_order == search_sort_order.asc:
            query = query.order_by(order_by.asc())
        else:
            query = query.order_by(order_by.desc())
        
        if search_page:
            query = query.offset(int(search_page) * 5)

        results_db = connection.execute(query.limit(5))
        results = []
        prev = ""
        next_page = ""
        
        for row in results_db:
            results.append(
                {
                    "line_item_id": uuid.uuid1(),
                    "item_sku": str(row.total_potions_bought) + " " + str(row.potion_sku,),
                    "customer_name": row.customer_name,
                    "line_item_total": row.total_cost,
                    "timestamp": row.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                }
            )
        if search_page:
            prev = str(int(search_page) - 1) if int(search_page) > 0 else ""
            next_page = str(int(search_page) + 1) if len(results) >= 5 else ""
            if len(results) < 5:
                next_page = ""
        else:
            next_page =  "1" if len(results) >= 5 else ""
            
        response = {
            "previous": prev,
            "next": next_page,
            "results": results
        }
        return response


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
        cart_id = connection.execute(sqlalchemy.text("INSERT INTO carts (customer_class, customer_name) VALUES (:class, :name) RETURNING cart_id"), {"class": new_cart.character_class, "name": new_cart.customer_name}).scalar_one()
    return {"cart_id": cart_id}


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    quantity = cart_item.quantity
    with db.engine.begin() as connection:
        potion_id = connection.execute(sqlalchemy.text("SELECT id FROM potions WHERE potion_sku = :sku"), {"sku": item_sku}).scalar_one()
        # potion_inventory = connection.execute(sqlalchemy.text("SELECT quantity FROM potions WHERE potion_sku = :sku"), {"sku": item_sku}).scalar_one()
        # try:   # try to update the catalog so that customers don't try to buy at the same time and then I don't have enough?
        #     connection.execute(sqlalchemy.text("UPDATE catalog SET quantity = quantity - :q WHERE id = :id"), {"q": quantity, "id": potion_id})
        # except exc.IntegrityError as e:
        #     raise Exception(f"Cannot add to cart, in inventory: {potion_inventory}, trying to buy: {quantity}")
        print(f"cart_id: {cart_id}, potion sku: {item_sku}, quantity: {quantity}")
        potion_cost = connection.execute(sqlalchemy.text("SELECT price FROM potions WHERE potion_sku = :sku"), {"sku": item_sku}).scalar_one()
        # connection.execute(sqlalchemy.text("UPDATE carts SET total_potions_bought = total_potions_bought + :potions_bought, total_cost = total_cost + :cost WHERE cart_id = :id"), {"potions_bought": quantity, "cost": potion_cost * quantity, "id": cart_id})
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
        total_potions_bought = connection.execute(sqlalchemy.text("SELECT SUM(quantity) FROM cart_items WHERE cart_id = :id"), {"id": cart_id}).scalar_one()
        total_cost = connection.execute(sqlalchemy.text("SELECT SUM(gold_cost) FROM cart_items WHERE cart_id = :id"), {"id": cart_id}).scalar_one()
        connection.execute(sqlalchemy.text("UPDATE carts SET total_potions_bought = :potions_bought, total_cost = :cost WHERE cart_id = :id"), {"potions_bought": total_potions_bought, "cost": total_cost, "id": cart_id})
        tx_id = connection.execute(sqlalchemy.text("INSERT INTO overall_transactions (description, type) VALUES ('Cart checkout id :idd cost :cost bought :num potions', 'cart checkout') RETURNING id"), {"idd": cart_id, "cost": total_cost, "num": total_potions_bought}).scalar_one()
        connection.execute(sqlalchemy.insert(gold_ledger), 
                           [
                               {"transaction_id": tx_id, "gold_change": total_cost}
                           ])
        # connection.execute(sqlalchemy.text(f"UPDATE global_inventory SET gold = gold + :total"), {"total": total_cost})
        # get all the items in the cart
        potions = connection.execute(sqlalchemy.text("SELECT potion_id, quantity FROM cart_items WHERE cart_id = :id"), {"id": cart_id}).fetchall()
        for potion_id, quantity in potions:
            # update the potion inventory for all the items they got
            # connection.execute(sqlalchemy.text(f"UPDATE potions SET quantity = quantity - :potion_num WHERE id = :id"), {"potion_num": quantity, "id": potion_id})
            connection.execute(sqlalchemy.insert(potion_ledger), 
                           [
                               {"transaction_id": tx_id, "potion_id": potion_id, "quantity_change": quantity * -1}
                           ])
    return {"total_potions_bought": total_potions_bought, "total_gold_paid": total_cost}

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from datetime import datetime
from src.api import auth

router = APIRouter(
    prefix="/info",
    tags=["info"],
    dependencies=[Depends(auth.get_api_key)],
)

class Timestamp(BaseModel):
    day: str
    hour: int

# Edgeday: Thursday
# Bloomday: Friday
# Aracanaday: Saturday
# Hearthday: Sunday
# Crownday: Monday
# Blesseday: Tuesday
# Soulday: Wednesday

@router.post("/current_time")
def post_time(timestamp: Timestamp):
    """
    Share current time.
    """
    current_day = datetime.now().strftime("%A")
    current_hour = datetime.now().hour
    days_map = {
        "Thursday": "Edgeday",
        "Friday": "Bloomday",
        "Saturday": "Aracanaday",
        "Sunday": "Hearthday",
        "Monday": "Crownday",
        "Tuesday": "Blesseday",
        "Wednesday": "Soulday"
    }
    string_of_the_day = days_map.get(current_day)
    return {"day": string_of_the_day, "hour": current_hour}


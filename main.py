import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("DELTA_SUPABASE_URL", "your-supabase-url")
SUPABASE_KEY = os.getenv("DELTA_SUPABASE_KEY", "your-supabase-anon-key")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Country code mapping
COUNTRY_CODE_MAP = {
    "Australia": "au",
    "Bahrain": "bh",
    "Saudi Arabia": "sa",
    "Japan": "jp",
    "China": "cn",
    "United States": "us",
    "Italy": "it",
    "Monaco": "mc",
    "Canada": "ca",
    "Spain": "es",
    "Austria": "at",
    "UK": "gb",
    "Hungary": "hu",
    "Belgium": "be",
    "Netherlands": "nl",
    "Singapore": "sg",
    "Azerbaijan": "az",
    "Mexico": "mx",
    "Brazil": "br",
    "Qatar": "qa",
    "UAE": "ae",
    "USA": "us",
}



# Pydantic models
class Race(BaseModel):
    id: int
    round: int
    name: str
    circuit: str
    country: str
    countryCode: str
    date: str
    year: int


class DriverColors(BaseModel):
    main: str
    accent: str
    secondary: Optional[str] = None

class Driver(BaseModel):
    driverCode: str;
    cost: float;
    driverName: str;
    teamName: str;
    deltaCost: float;
    driverImage: str;
    teamImage: str;
    colors: DriverColors;


class ErgastLocation(BaseModel):
    lat: str
    long: str
    locality: str
    country: str

class ErgastCircuit(BaseModel):
    circuitId: str
    url: str
    circuitName: str
    Location: ErgastLocation

class ErgastRace(BaseModel):
    season: str
    round: str
    url: str
    raceName: str
    Circuit: ErgastCircuit
    date: str
    time: Optional[str] = None

class ErgastRaceTable(BaseModel):
    season: str
    Races: List[ErgastRace]

class ErgastMRData(BaseModel):
    RaceTable: ErgastRaceTable

class ErgastResponse(BaseModel):
    MRData: ErgastMRData



app = FastAPI(title = "Delta F1 API", version= "1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Your React app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Delta F1 API is running!"}

def get_country_code(country: str) -> str:
    """Get country code from country name"""
    return COUNTRY_CODE_MAP.get(country, "F1")





def transform_ergast_race_to_race(ergast_race: ErgastRace, index: int) -> Race:
    """Transform Ergast API race data to our Race model"""
    race_date = datetime.fromisoformat(ergast_race.date)
    today = datetime.now()
    
    return Race(
        id=int(ergast_race.round),
        round=int(ergast_race.round),
        name=ergast_race.raceName,
        circuit=ergast_race.Circuit.circuitName,
        country=ergast_race.Circuit.Location.country,
        countryCode=get_country_code(ergast_race.Circuit.Location.country),
        date=ergast_race.date + "T" + (ergast_race.time if ergast_race.time is not None else "00:00:00"),
        year=int(ergast_race.season),
    )

async def fetch_drivers_from_supabase() -> List[Driver]:
    """Fetch drivers from Supabase database"""
    try:
        # Query the drivers table
        response = supabase.table('drivers').select('*').execute()
        
        drivers = []
        for driver_data in response.data:
            # Create DriverColors object
            colors = DriverColors(
                main=driver_data['color_main'],
                accent=driver_data['color_accent'],
                secondary=driver_data.get('color_secondary')
            )
            
            # Create Driver object
            driver = Driver(
                driverCode=driver_data['driver_code'],
                cost=float(driver_data['cost']),
                driverName=driver_data['driver_name'],
                teamName=driver_data['team_name'],
                deltaCost=float(driver_data['delta_cost']),
                driverImage=driver_data.get('driver_image', ''),
                teamImage=driver_data.get('team_image', ''),
                colors=colors
            )
            drivers.append(driver)
        
        return drivers
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching drivers from database: {str(e)}")


async def fetch_races_from_ergast(year: int | None = None) -> List[Race]:
    """Fetch races from Ergast API"""
    if year is None:
        year = datetime.now().year
    
    url = f"https://api.jolpi.ca/ergast/f1/{year}.json"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            
            ergast_data = ErgastResponse(**response.json())
            races = [
                transform_ergast_race_to_race(race, i) 
                for i, race in enumerate(ergast_data.MRData.RaceTable.Races)
            ]
            
            return races
            
        except httpx.HTTPError as e:
            raise HTTPException(status_code=503, detail=f"Failed to fetch races from Ergast API: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing race data: {str(e)}")

@app.get("/api/races", response_model=List[Race])
async def get_races(year: Optional[int] = None):
    """
    Get F1 races for the specified year (defaults to current year)
    
    - **year**: Year to get races for (optional, defaults to current year)
    """
    races = await fetch_races_from_ergast(year)
    return races

# Driver endpoint
@app.get("/api/drivers", response_model=List[Driver])
async def get_drivers():
    """
    Get F1 drivers from the database
    """
    drivers = await fetch_drivers_from_supabase()
    return drivers

@app.get("/api/drivers/images")
async def get_driver_images():
    drivers = await fetch_drivers_from_supabase()
    return {driver.driverCode: driver.driverImage for driver in drivers if driver.driverImage}


@app.get("/api/races/upto", response_model =List[Race])
async def get_upto_next_races(): 
    """
    Get F1 races for the current year up to the next race based on the current date. Returns in reverse order.
    """

    races = await get_races()
    current_date = datetime.now(timezone.utc)
    added = False
    output = []

    for race in races:
        if datetime.fromisoformat(race.date) <= current_date:
            output.append(race)
        else:
            if not added:
                output.append(race)
                added = True
    
    output.reverse()

    return output

@app.get("/api/race/{round}", response_model=Race)
async def get_race(round: int):
    """Get a specific race by ID"""
    races = await get_races()
    
    for race in races:
        if race.id == round:
            return race
    
    raise HTTPException(status_code=404, detail="Race not found")
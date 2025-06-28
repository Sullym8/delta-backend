from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
from datetime import datetime, timedelta

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

DRIVER_TEAM_MAP = {
    "ALB": "Williams Racing",
    "SAI": "Williams Racing", 
    "VER": "Red Bull Racing",
    "TSU": "Red Bull Racing",
    "HAM": "Ferrari",
    "LEC": "Ferrari",
    "NOR": "McLaren Racing",
    "PIA": "McLaren Racing",
    "RUS": "Mercedes",
    "ANT": "Mercedes",
    "ALO": "Aston Martin",
    "STR": "Aston Martin",
    "BEA": "Haas F1 Team",
    "OCO": "Haas F1 Team",
    "GAS": "Alpine F1 Team",
    "COL": "Alpine F1 Team",
    "HAD": "RB F1 Team",
    "LAW": "RB F1 Team",
    "BOR": "Kick Sauber",
    "HUL": "Kick Sauber", 
}

TEAM_COLORS = {
    "Williams Racing": {
        "main": "#041E42",
        "accent": "#FFFFFF",
    },
    "Red Bull Racing": {
        "main": "#001526",
        "accent": "#0073D0",
    },
    "Ferrari": {
        "main": "#B41726",
        "accent": "#FFFFFF",
        "secondary": "#B41726"
    },
    "McLaren Racing": {
        "main": "#DE6A10",
        "accent": "#000000",
        "secondary": "#FF8700"
    },
    "Mercedes": {
        "main": "#00d7b7",
        "accent": "#000000",
        "secondary": "#FFFFFF"
    },
    "Aston Martin": {
        "main": "#0A5A4F",
        "accent": "#CEDC00",
    },
    "Haas F1 Team": {
        "main": "#000",
        "accent": "#D92A1C",
        "secondary": "#FFFFFF"
    },
    "Alpine F1 Team": {
        "main": "#061A4D",
        "accent": "#FF87BC",
    },
    "RB F1 Team": {
        "main": "#1433C9",
        "accent": "#FFFFFF",
    },
    "Kick Sauber": {
        "main": "#07C00F",
        "accent": "#00000",
    }
}

TEAM_IMAGES = {
    "Williams Racing": "src/assets/williams.avif",
    "Red Bull Racing": "src/assets/redbull.avif",
    "Ferrari": "src/assets/ferrari.avif",
    "McLaren Racing": "src/assets/mclaren.avif",
    "Mercedes": "src/assets/mercedes.avif",
    "Aston Martin": "src/assets/aston_martin.avif",
    "Haas F1 Team": "src/assets/haas.avif",
    "Alpine F1 Team": "src/assets/alpine.avif",
    "RB F1 Team": "src/assets/vcarb.avif",
    "Kick Sauber": "src/assets/kick_sauber.avif"
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

# Driver API models
class ErgastDriver(BaseModel):
    driverId: str
    permanentNumber: str
    code: str
    url: str
    givenName: str
    familyName: str
    dateOfBirth: str
    nationality: str

class ErgastDriverTable(BaseModel):
    season: str
    Drivers: List[ErgastDriver]

class ErgastDriverMRData(BaseModel):
    DriverTable: ErgastDriverTable

class ErgastDriverResponse(BaseModel):
    MRData: ErgastDriverMRData

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

def get_driver_image_url(driver_code: str, given_name: str, family_name: str) -> str:
    """Generate F1 official driver image URL"""
    # F1 official image pattern
    first_name_initials = given_name[:3].upper()
    last_name_initials = family_name[:3].upper()
    driver_id = f"{first_name_initials}{last_name_initials}01"
    
    # Official F1 media URL pattern
    return f"https://media.formula1.com/d_driver_fallback_image.png/content/dam/fom-website/drivers/{given_name[0].upper()}/{driver_id}_{given_name}_{family_name}/{driver_id.lower()}.png"

def transform_ergast_driver_to_driver(ergast_driver: ErgastDriver) -> Driver:
    """Transform Ergast API driver data to our Driver model"""
    driver_code = ergast_driver.code
    team_name = DRIVER_TEAM_MAP.get(driver_code)
    
    # Get colors for the team
    team_colors = TEAM_COLORS.get(team_name, {
        "main": "#FFFFFF",
        "accent": "#000000",
        "secondary": "#808080"
    })
    
    # Get cost (with some randomness for deltaCost)
    base_cost = 30.0
    delta_cost = round((hash(driver_code) % 21 - 10) / 10, 1)  # Random delta between -1.0 and 1.0
    
    return Driver(
        driverCode=driver_code,
        cost=base_cost,
        driverName=f"{ergast_driver.givenName} {ergast_driver.familyName}",
        teamName=team_name,
        deltaCost=delta_cost,
        driverImage=get_driver_image_url(driver_code, ergast_driver.givenName, ergast_driver.familyName),
        teamImage=TEAM_IMAGES.get(team_name, "/assets/default.avif"),
        colors=DriverColors(**team_colors)
    )

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
        date=ergast_race.date,
    )

async def fetch_drivers_from_ergast(year: int = None) -> List[Driver]:
    """Fetch drivers from Ergast API"""
    if year is None:
        year = datetime.now().year
    
    url = f"https://api.jolpi.ca/ergast/f1/{year}/drivers.json"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            
            ergast_data = ErgastDriverResponse(**response.json())
            drivers = [
                transform_ergast_driver_to_driver(driver) 
                for driver in ergast_data.MRData.DriverTable.Drivers
                if driver.code in DRIVER_TEAM_MAP
            ]
            
            return drivers
            
        except httpx.HTTPError as e:
            raise HTTPException(status_code=503, detail=f"Failed to fetch drivers from Ergast API: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing driver data: {str(e)}")


async def fetch_races_from_ergast(year: int = None) -> List[Race]:
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
async def get_drivers(year: Optional[int] = None):
    """
    Get F1 drivers for the specified year (defaults to current year)
    
    - **year**: Year to get drivers for (optional, defaults to current year)
    """
    drivers = await fetch_drivers_from_ergast(year)
    return drivers

@app.get("/api/races/upto", response_model =List[Race])
async def get_upto_next_races(): 
    """
    Get F1 races for the current year up to the next race based on the current date. Returns in reverse order.
    """

    races = await get_races()
    current_date = datetime.now()
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
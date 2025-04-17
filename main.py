import osmnx as ox
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from shapely.geometry import Point
import datetime as dt
import re
from geopy.distance import geodesic

class DataObject:
    def dataPull(self, city:str="Währing, Wien, Austria",name:str=None):
        print(f"Initializing DataPull... {self.city}")
        self.city = city
        self.restaurants = []
        
        tags = {'amenity': ['restaurant', 'pub', 'cafe', 'fast_food', 'bar', 'food_court', 'biergarten', 'ice_cream']}
        restaurants = ox.features_from_place(self.city, tags)
        # print(restaurants.columns)
        # print(restaurants.index)
        def get_cuisine_or_amenity(row):
            if row['amenity'] == 'restaurant' and pd.notna(row['cuisine']):
                return row['cuisine']
            else:
                return row['amenity']
            
        restaurants['cuisine_or_amenity'] = restaurants.apply(get_cuisine_or_amenity, axis=1)

        geolocator = Nominatim(user_agent="my_geocoder")
        geocode = RateLimiter(geolocator.reverse, min_delay_seconds=1)
        def get_address(row):
            if pd.isna(row['addr:street']) or pd.isna(row['addr:housenumber']) or pd.isna(row['addr:city']) or pd.isna(row['addr:postcode']):
                lat = row['lat']
                long = row['long']
                try:
                    location = geocode((lat, long))
                    if location:
                        address = location.raw['address']
                        row['addr:street'] = address.get('road', None)
                        row['addr:housenumber'] = address.get('house_number', None)
                        row['addr:city'] = address.get('city', address.get('town', address.get('village', None)))
                        row['addr:postcode'] = address.get('postcode', None)
                except Exception as e:
                    print(f"Error geocoding: {e}") 
            return pd.Series(row)

        
        restaurants['id'] = [i[1] for i in restaurants.index]
        restaurants["lat"] = restaurants['geometry'].apply(lambda x: re.search(r'(\d+[.]{1}\d+[ ]\d+[.]{1}\d+)', str(x)).group(0).split(" ")[0])
        restaurants["long"] = restaurants['geometry'].apply(lambda x: re.search(r'(\d+[.]{1}\d+[ ]\d+[.]{1}\d+)', str(x)).group(0).split(" ")[1])
        restaurants = restaurants.drop(columns=['geometry'])
        restaurants = restaurants.apply(get_address, axis=1)
        self.data = restaurants[['id', 'name', 'lat', 'long', 'addr:street', 'addr:housenumber', 'addr:city', 'addr:postcode', "cuisine_or_amenity","opening_hours"]].dropna(subset=['name'])
        print(self.data.head())
        print("Data Pulled...")
        self.writeToCSV(name=name)
        return self.data
    def addData(self, CSVName:str=None):
        if CSVName is None:
            raise ValueError("CSVName cannot be None")
        try:
            df = pd.read_csv(CSVName+".csv", encoding="utf-8-sig")
        except:
            raise FileNotFoundError(f"File {CSVName} not found")
        self.data=df
        print(f"Data added from {CSVName}")
    def __init__(self, dataBrought:bool=True, city:str="Währing, Wien, Austria", name:str=None):
        self.city = city
        if dataBrought:
            self.addData(name)
        else:
            self.dataPull(self.city,name=name)
    
    def writeToCSV(self,name:str=None):
        if name is None:
            name = self.city.replace(",","").replace(" ","_")
        self.data.to_csv(f"{name}.csv", encoding="utf-8-sig",index=False)
        print(f"Data written to {name}.csv")
class Location:
    def __init__(self, lat, long, district, street, house):
        self.lat = lat
        self.long = long
        self.district = district
        self.street = street
        self.house = house
    def __str__(self):
        return f"{self.street} {self.house}, {self.district}"
def ParseHours(inputString):
    dayMap = ["Mo","Tu","We","Th","Fr","Sa","Su","PH"]
    NormalDayMap = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun","PH"]
    patternA = re.compile(r'(?P<days>(?:PH|Mo|Tu|We|Th|Fr|Sa|Su)(?:[-,](?:PH|Mo|Tu|We|Th|Fr|Sa|Su))*)\s+(?P<hours>(?:\d{2}:\d{2}-\d{2}:\d{2})(?:,\d{2}:\d{2}-\d{2}:\d{2})*)')
    patternB = re.compile(r'(?P<days>(?:PH|Mo|Tu|We|Th|Fr|Sa|Su))')
    schedule = {}
    matches = patternA.finditer(inputString)
    if [i for i in matches] == []:
        for i in NormalDayMap:
            schedule[i] = inputString
    else:
        matches = patternA.finditer(inputString)
        for match in matches:
            daysPart = match.group('days')
            hoursPart = match.group('hours')
            if "," in hoursPart:
                hoursPart = hoursPart.split(",")
            if "-" in daysPart:
                if "," in daysPart:
                    daysPart = daysPart.split(",")
                    soloDays = [day for day in daysPart if "-" not in day]
                    for i in soloDays:
                        schedule[NormalDayMap[dayMap.index(i)]] = hoursPart
                    daysPart = str([day for day in daysPart if day not in soloDays]).replace("[","").replace("]","").replace("'","")
                start, end = daysPart.split('-')
                for i in range(dayMap.index(start), dayMap.index(end)+1):
                    schedule[NormalDayMap[i]] = hoursPart
            else:
                subDays = patternB.findall(daysPart)
                for i in subDays:
                    schedule[NormalDayMap[dayMap.index(i)]] = hoursPart
    return schedule
class OpenHours:
    def __init__(self, hours:str=None):
        if hours is None:
            raise ValueError("hours cannot be None")
        if str(hours) != 'nan':
            self.hours = ParseHours(hours)
        else:
            self.hours = None
    def __str__(self):
        return str(self.hours)
    def __getitem__(self, key):
        return self.hours.get(key) if self.hours else None
    
class Restaurant:
    def __init__(self, id, name, cuisine, location:Location, hours:OpenHours):
        self.id = id
        self.name = name
        self.cuisine = cuisine
        self.hours = hours
        self.location = location
    def __getitem__(self, key):
        if hasattr(self, key):
            return getattr(self, key)
        if self.hours and self.hours.hours:
            return self.hours.hours.get(key)
        raise KeyError(f"{key} not found in Restaurant or DataBase")
    def __str__(self):
        return f"{self.id} {self.name} ({self.cuisine}) - {self.location} - {self.distanceFrom} km"
    def distanceFromCrow(self, address):
        userPoint = ox.geocoder.geocode(address)
        resPoint = Point(float(self.location.lat), float(self.location.long))
        self.distanceFrom = geodesic((userPoint[0], userPoint[1]), (resPoint.y, resPoint.x)).kilometers
        return self.distanceFrom
    def isCurrentlyOpen(self):
        #dt.datetime.now()
        day = dt.datetime.now().strftime("%a")
        currentTime = dt.datetime.now().strftime("%H:%M")
        currentTime = dt.datetime.strptime(currentTime, "%H:%M").time()
        if self.hours is None:
            return False
        hours = self.hours.hours[day]
        if ',' in hours:
            hours = hours.split(',')
            for i in hours:
                start, end = i.split("-")
                start_time = dt.datetime.strptime(start, "%H:%M").time()
                end_time = dt.datetime.strptime(end, "%H:%M").time()
                current_time = dt.datetime.strptime(time, "%H:%M").time()
                if start_time <= current_time <= end_time:
                    return True
            return False
        else:
            start, end = hours.split("-")
            if start == "24:00":
                start = "23:59"
            if end == "24:00":
                end = "23:59"
            startTime = dt.datetime.strptime(start, "%H:%M").time()
            endTime = dt.datetime.strptime(end, "%H:%M").time()
            if startTime <= currentTime <= endTime:
                return True
            else:
                return False
class DataBase(DataObject):
    def __init__(self, city:str="Währing, Wien, Austria", name:str=None, dataBrought:bool=False):
        self.city = city
        self.restaurants = []
        self.dataBrought = dataBrought
        self.dataPull = DataObject(dataBrought=self.dataBrought, city=self.city, name=name)
        self.restaurants = self.dataPull.data
        self.restaurants = [Restaurant(row['id'], row['name'], row['cuisine_or_amenity'], Location(row['lat'],row['long'], row['addr:city'], row['addr:street'], row['addr:housenumber']), OpenHours(row['opening_hours'])) for index, row in self.restaurants.iterrows()]
    def __getitem__(self, key):
        if hasattr(self, key):
            return getattr(self, key)
    def getRestaurants(self):
        return [str(x) for x in self.restaurants]
    
    def getRestaurantByName(self, name:str):
        answer = [x for x in self.restaurants if x.name == name]
        if len(answer) == 1:
            return answer[0]
        else:
            return answer    
    # def getRestaurantByLocation(self, lat:float, long:float):
    #     return [x for x in self.restaurants if x.location.lat == lat and x.location.long == long]
    def getClosestList(self, address:str, n:int=5):
        for i in self.restaurants:
            i.distanceFromCrow(address)
        self.restaurants.sort(key=lambda x: x.distanceFrom)
        return [str(x) for x in self.restaurants[:n]]
import osmnx as ox
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from shapely.geometry import Point
import re

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
class OpenHours:
    def __init__(self, open, close):
        self.open = open
        self.close = close
        
class Restaurant:
    def __init__(self, id, name, cuisine, location):
        self.id = id
        self.name = name
        self.cuisine = cuisine
        self.location = location
    def __str__(self):
        return f"{self.id} {self.name} ({self.cuisine}) - {self.location}"
    def isCurrentlyOpen(self):
        # Placeholder for actual implementation
        return True
class DataBase(DataObject):
    def __init__(self, city:str="Währing, Wien, Austria", name:str=None, dataBrought:bool=False):
        self.city = city
        self.restaurants = []
        self.dataBrought = dataBrought
        self.dataPull = DataObject(dataBrought=self.dataBrought, city=self.city, name=name)
        self.restaurants = self.dataPull.data
        self.restaurants = [Restaurant(row['id'], row['name'], row['cuisine_or_amenity'], Location(row['lat'],row['long'], row['addr:city'], row['addr:street'], row['addr:housenumber'])) for index, row in self.restaurants.iterrows()]
    
    def getRestaurants(self):
        return [str(x) for x in self.restaurants]
    
    def getRestaurantByName(self, name:str):
        return [x for x in self.restaurants if x.name == name]
    
    def getRestaurantByLocation(self, lat:float, long:float):
        return [x for x in self.restaurants if x.location.lat == lat and x.location.long == long]
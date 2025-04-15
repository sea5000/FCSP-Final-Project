import osmnx as ox
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from shapely.geometry import Point

class DataPull:
    def dataPull(self, city:str="Währing, Wien, Austria"):
        self.city = city
        self.restaurants = []
        
        tags = {'amenity': ['restaurant', 'pub', 'cafe', 'fast_food', 'bar', 'food_court', 'biergarten', 'ice_cream']}
        restaurants = ox.features_from_place(self.city, tags)

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
                point = row['geometry']
                if isinstance(point, Point):
                    try:
                        location = geocode((point.y, point.x))
                        if location:
                            address = location.raw['address']
                            row['addr:street'] = address.get('road', None)
                            row['addr:housenumber'] = address.get('house_number', None)
                            row['addr:city'] = address.get('city', address.get('town', address.get('village', None)))
                            row['addr:postcode'] = address.get('postcode', None)
                    except Exception as e:
                        print(f"Error geocoding: {e}") 
            return pd.Series(row)

        restaurants = restaurants.apply(get_address, axis=1)
        self.restaurants = restaurants[['name', 'geometry', 'addr:street', 'addr:housenumber', 'addr:city', 'addr:postcode', "cuisine_or_amenity","opening_hours"]].dropna(subset=['name'])
        print(self.restaurants.head())
        print("Data Pulled...")
        return self.restaurants
        
    def __init__(self, city:str="Währing, Wien, Austria"):
        self.city = city
        print(f"Initializing DataPull... {self.city}")
        self.restaurants = self.dataPull(self.city)
    
    def writeToCSV(self,name:str=None):
        if name is None:
            name = self.city.replace(",","").replace(" ","_")
        self.restaurants.to_csv(f"{name}.csv", encoding="utf-8-sig",index=False)





import osmnx as ox
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from shapely.geometry import Point
import datetime as dt
import re
from geopy.distance import geodesic
from pyproj import CRS, Transformer
import requests
import json
import time 

class DataObject:
    def dataPull(self, city:str="Währing, Wien, Austria",name:str=None,populateAddress=True):
        print(f"Initializing DataPull... {self.city}")
        self.city = city
        self.restaurants = []
        
        tags = {'amenity': ['restaurant', 'pub', 'cafe', 'fast_food', 'bar', 'food_court', 'biergarten', 'ice_cream']}
        print("Pulling Data from OSM...")
        restaurants = ox.features_from_place(self.city, tags)
        def get_cuisine_or_amenity(row):
            if row['amenity'] == 'restaurant' and pd.notna(row['cuisine']):
                return row['cuisine']
            else:
                return row['amenity']
            
        restaurants['cuisine_or_amenity'] = restaurants.apply(get_cuisine_or_amenity, axis=1)

        # geolocator = Nominatim(user_agent="my_geocoder")
        # geocode = RateLimiter(geolocator.reverse, min_delay_seconds=1)
        
        restaurants['id'] = [i[1] for i in restaurants.index]
        restaurants["lat"] = restaurants['geometry'].apply(lambda x: re.search(r'(\d+[.]{1}\d+[ ]\d+[.]{1}\d+)', str(x)).group(0).split(" ")[0])
        restaurants["long"] = restaurants['geometry'].apply(lambda x: re.search(r'(\d+[.]{1}\d+[ ]\d+[.]{1}\d+)', str(x)).group(0).split(" ")[1])
        restaurants = restaurants.drop(columns=['geometry'])
        if populateAddress:
            print("Getting Addresses...")
            start_time = time.time()
            for index, row in restaurants.iterrows():
                lat = row['lat']
                long = row['long']
                crs_wgs84 = CRS("EPSG:4326")
                crs_epsg31256 = CRS("EPSG:31256")
                transformer = Transformer.from_crs(crs_wgs84, crs_epsg31256, always_xy=True)
                easting, northing = transformer.transform(lat, long)
                url = f"https://data.wien.gv.at/daten/OGDAddressService.svc/ReverseGeocode?location={easting},{northing}&crs=EPSG:31256&type=A3:8012"
                
                retries = 5
                for attempt in range(retries):
                    try:
                        response = requests.get(url, timeout=10)
                        if response.status_code == 200:
                            data = json.loads(response.text)
                            row['addr:street'] = data['features'][0]['properties']['StreetName']
                            row['addr:housenumber'] = data['features'][0]['properties']['StreetNumber']
                            row['addr:city'] = data['features'][0]['properties']['Municipality']
                            row['addr:postcode'] = data['features'][0]['properties']['PostalCode']
                            restaurants.loc[index] = row
                            break
                        else:
                            print(f"Request failed with status code: {response.status_code}")
                    except requests.exceptions.Timeout:
                        print(f"Request timed out (attempt {attempt + 1}/{retries}). Retrying...")
                    except requests.exceptions.RequestException as e:
                        print(f"Request failed (attempt {attempt + 1}/{retries}): {e}")
                    time.sleep(2 ** attempt)
                
                elapsed_time = time.time() - start_time
                if elapsed_time >= 1200:
                    print("Pausing for 4 minutes...")
                    time.sleep(240)
                    start_time = time.time()

                    
        self.data = restaurants[['id', 'name', 'lat', 'long', 'addr:street', 'addr:housenumber', 'addr:city', 'addr:postcode', "cuisine_or_amenity","opening_hours"]].dropna(subset=['name'])
        print(self.data.head())
        print("Data Pulled. Writing...")
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
    patternTimeDG = re.compile(r'((\w+|\-|\,)+ (\d{2}:\d{2}-\d{2}:\d{2}))')
    patternDays = re.compile(r'(PH|Mo|Tu|We|Th|Fr|Sa|Su)')
    patternDayRange = re.compile(r'((?:PH|Mo|Tu|We|Th|Fr|Sa|Su)\-*(?:PH|Mo|Tu|We|Th|Fr|Sa|Su))')
    patternDaysOff = re.compile(r'([(PH|Mo|Tu|We|Th|Fr|Sa|Su)\, ]+) (?:off|closed)') #(?:(?<=^)|(?<=;|\s))\s*((?:PH|Mo|Tu|We|Th|Fr|Sa|Su)(?:\s*,\s*(?:PH|Mo|Tu|We|Th|Fr|Sa|Su))*)\s*\b(?:off)\b
    patternHours = re.compile(r'(?P<hours>(\d{2}:\d{2}-\d{2}:\d{2}))')
    schedule = {}
    if ";" in inputString:
        modInputString = inputString.split(";")
        for a in modInputString:
            days = patternDayRange.findall(a)
            if days != [] and len(days) == 1:
                rangeV = [dayMap.index(i) for i in days[0].split("-")]
                rangeV.sort()
                rangeV[1] += 1
                hours = patternHours.findall(a)
                for i in range(rangeV[0],rangeV[1]):
                    if hours != []:
                        schedule[NormalDayMap[i]] = list(set(hours[0]))
            if ("off" in a or "geschlossen" in a or "closed" in a or "OFF" in a) and "offen" not in a:
                days = patternDaysOff.findall(a)
                if any([True for m in days if ',' in m]):
                    daysMod = days[0].strip().split(",")
                    for day in daysMod:
                        if day in dayMap:
                            schedule[NormalDayMap[dayMap.index(day.strip())]] = "OFF"
                else:
                    if len(days) == 1:
                        if days != []:
                            subDays = patternDays.findall(days[0])
                            if len(subDays) > 1:
                                for day in subDays:
                                    if day in dayMap:
                                        schedule[NormalDayMap[dayMap.index(day.strip())]] = patternHours.findall(a)
                            else:
                                if days[0] in dayMap:
                                    schedule[NormalDayMap[dayMap.index(days[0].strip())]] = patternHours.findall(a)
                    else:
                        if days!= []:
                            schedule[NormalDayMap[dayMap.index(days)]] = patternHours.findall(a)
            if any([True for i in a if ',' in i]):
                days = patternDays.findall(a)
                if len(days) > 1:
                    for b in days:
                        days = patternDays.findall(b)
                        hours = patternHours.findall(b)
                        for day in days:
                            if hours != []:
                                schedule[NormalDayMap[dayMap.index(day)]] = list(set(hours[0]))
                else:
                    if days != []:
                        schedule[NormalDayMap[dayMap.index(days[0])]] = patternHours.findall(days[0])
    elif len(patternTimeDG.findall(inputString)) == 0 and len(patternDays.findall(inputString)) == 0 and len(patternHours.findall(inputString)) == 1:
        for day in NormalDayMap:
            schedule[day] = inputString
    else:
        groups = patternTimeDG.findall(inputString)
        for a in groups:
            a = a[0]
            days = patternDayRange.findall(a)
            if days != [] and len(days) == 1:
                rangeV = [dayMap.index(i) for i in days[0].split("-")]
                rangeV.sort()
                rangeV[1] += 1
                
                hours = patternHours.findall(a)
                for i in range(rangeV[0],rangeV[1]):
                    if hours != []:
                        schedule[NormalDayMap[i]] = list(set(hours[0]))
            elif ("off" in a or "geschlossen" in a or "closed" in a or "OFF" in a) and "offen" not in a:
                days = patternDaysOff.findall(a)
                if days == []:
                    continue
                if any([True for m in days if ',' in m]):
                    daysMod = days[0].split(",")
                    for day in daysMod:
                        if day in dayMap:
                            schedule[NormalDayMap[dayMap.index(day.strip())]] = patternHours.findall(a)
                else:
                    if len(days) == 1:
                        subDays = patternDays.findall(days[0])
                        if len(subDays) > 1:
                            for day in subDays:
                                if day in dayMap:
                                    schedule[NormalDayMap[dayMap.index(day.strip())]] = patternHours.findall(a)
                        else:
                            if days[0] in dayMap:
                                schedule[NormalDayMap[dayMap.index(days[0].strip())]] = patternHours.findall(a)
                    else:
                        if days!= []:
                            schedule[NormalDayMap[dayMap.index(days)]] = patternHours.findall(a)
            elif ',' in a:
                days = patternDays.findall(a)
                hours = patternHours.findall(a)
                if len(days) > 1:
                    for b in days:
                        if b != [] or b != '':
                            schedule[NormalDayMap[dayMap.index(b)]] = list(set(hours[0]))
                else:
                    if days != []:
                        schedule[NormalDayMap[dayMap.index(days[0])]] = list(set(hours[0]))
    
    # if schedule == {} and inputString != '':
    #     raise ValueError("Invalid inputString")
    return schedule

class OpenHours:
    def __init__(self, hours:str=None):
        if hours is None:
            raise ValueError("hours cannot be None")
        if str(hours) != 'nan':
            hours = re.sub(r'(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})', r'\1-\2', hours)
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
        if self.__getattribute__("queryScore") is None:
            return f"{self.id} - {self.name} ({self.cuisine}) - {self.location} - {self.distanceFrom} km"
        else:
            return f"{self.id} - {self.name} ({self.cuisine}) - {self.location} - {self.distanceFrom} km - {self.queryScore}"
    def distanceFromCrow(self, address):
        userPoint = ox.geocoder.geocode(address)
        resPoint = Point(float(self.location.lat), float(self.location.long))
        self.distanceFrom = geodesic((userPoint[0], userPoint[1]), (resPoint.y, resPoint.x)).kilometers
        return self.distanceFrom
    # def distanceFromPT(self, address):
        # url = "http://www.wienerlinien.at/ogd_routing/XML_TRIP_REQUEST2"

        # params = {
        #     "sessionID": "0",
        #     "type_origin": "stopID",
        #     "name_origin": "60201468",         # Westbahnhof stop ID
        #     "type_destination": "stopID",
        #     "name_destination": "60201320",    # Stephansplatz stop ID
        #     "itdDate": "20250418",             # Date in YYYYMMDD
        #     "itdTime": "1030",                 # Time in HHMM
        #     "itdTripDateTimeDepArr": "dep",    # dep or arr
        #     "ptOptionsActive": "1",
        #     "excludedMeans": "4",              # Exclude trams
        #     "outputFormat": "XML"
        # }

        # response = requests.get(url, params=params)
        # print("Status:", response.status_code)
        # print(response.text)  # or write to file to examine more easily
        # with open("response.xml", "w", encoding="utf-8") as f:
        #     f.write(response.text)


        # import xml.etree.ElementTree as ET

        # # Load the XML file
        # tree = ET.parse('response.xml')
        # root = tree.getroot()

        # # Namespace helper (some tags may include namespaces)
        # ns = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}

        # # Find all routes
        # routes = root.findall(".//itdRoute")

        # # Loop through routes and extract info
        # for i, route in enumerate(routes, 1):
        #     print(f"\n=== 🚆 Route Option {i} ===")
            
        #     # Travel time
        #     duration = route.attrib.get("publicDuration")
        #     print(f"🕒 Duration: {duration}")
    def isCurrentlyOpen(self):
        day = dt.datetime.now().strftime("%a")
        currentTime = dt.datetime.now().strftime("%H:%M")
        currentTime = dt.datetime.strptime(currentTime, "%H:%M").time()
        if self.hours.hours is None:
            return "No Data"
        if day not in self.hours.hours:
            return False
        hours = self.hours.hours[day]
        if hours == "OFF":
            return False
        if type(hours) == list and len(hours) > 1:
            for i in hours:
                start, end = i.split("-")
                if start == "24:00":
                    start = "23:59"
                if end == "24:00":
                    end = "23:59"
                if int(end[:2]) > 23:
                    end = f"{int(end[:2])-24}:{end[-2:]}"
                start_time = dt.datetime.strptime(start, "%H:%M").time()
                end_time = dt.datetime.strptime(end, "%H:%M").time()
                current_time = dt.datetime.strptime(time, "%H:%M").time()
                if start_time <= current_time <= end_time:
                    return True
            return False            
        else:
            if type(hours) != str:
                for i in hours:
                    start, end = i.split("-")
                    if start == "24:00":
                        start = "23:59"
                    if end == "24:00":
                        end = "23:59"
                    if int(end[:2]) > 23:
                        end = f"{int(end[:2])-24}:{end[-2:]}"
                    startTime = dt.datetime.strptime(start, "%H:%M").time()
                    endTime = dt.datetime.strptime(end, "%H:%M").time()
                    if startTime <= currentTime <= endTime:
                        return True
                    else:
                        return False
            else:
                start, end = hours.split("-")
                if start == "24:00":
                    start = "23:59"
                if end == "24:00":
                    end = "23:59"
                if int(end[:2]) > 23:
                    end = f"{int(end[:2])-24}:{end[-2:]}"
                startTime = dt.datetime.strptime(start, "%H:%M").time()
                endTime = dt.datetime.strptime(end, "%H:%M").time()
                if startTime <= currentTime <= endTime:
                    return True
                else:
                    return False
class SearchQuery:
    def __init__(self, cuisine:str=None, Diststance:int=None, District:str=None, OpenNow:bool=False):
        self.cuisine = cuisine
        self.Diststance = Diststance
        self.District = District
        self.OpenNow = OpenNow
    def __str__(self):
        return f"Looking for {self.cuisine} within {self.Diststance}km of the user {"that is open now" if self.OpenNow == True else "that is not open now"}"
    def setQueryParameters(self, cuisine:str=None, Diststance:int=None, District:str=None, OpenNow:bool=False):
        self.cuisine = cuisine
        self.Diststance = Diststance
        self.District = District
        self.OpenNow = OpenNow
        return [self.query, self.cuisine, self.location, self.hours]
    def menu(self):
        instructions = set()
        print("Select your search parameters:")
        print("1. Cuisine")
        print("2. Distance")
        print("3. District")
        print("4. Open Now")
        print("5. Done")
        choice = input("Enter any combination of the above choice (ie 143 or 1,3,2): ")
        if choice == '5':
            return False
        if choice == 'q':
            print("Exiting...")
            return False
        if choice == '':
            print("No choice made, please try again.")
            return True
        if ',' in choice:
            choice = choice.split(",")
            for i in choice:
                instructions.add(int(i))
        if choice.isdigit():
            choice = [int(i) for i in choice]
            for i in choice:
                instructions.add(int(i))
        for i in instructions:
            if i == 1:
                self.cuisine = input("Enter cuisine: ").lower()
            elif i == 2:
                self.Diststance = float(input("Enter distance (km): "))
            elif i ==   3:
                self.District = str(int(input("Enter district: ")))
                # print(self.District)
            elif i == 4:    
                self.OpenNow = input("Open now? (y/n): ")
                if self.OpenNow == "y":
                    self.OpenNow = True
                elif self.OpenNow == "n":
                    self.OpenNow = False

    def evaluateQuery(self, restaurant:Restaurant):
        if self.District == restaurant.location.district:
            print(self.District,restaurant.location.district)
        score = 0
        if self.cuisine is not None and restaurant.cuisine == self.cuisine:
            score += 1
        if self.Diststance is not None and restaurant.distanceFrom < self.Diststance:
            score += 1
        if self.District is not None and str(restaurant.location.district) == str(self.District):
            # print("DISTRICT CHECK")
            score += 1
        if self.OpenNow and restaurant.isCurrentlyOpen():
            score += 1
        return score
            
class DataBase(DataObject):
    def __init__(self, city:str="Währing, Wien, Austria", name:str=None, dataBrought:bool=True):
        self.city = city
        self.restaurants = []
        self.dataBrought = dataBrought
        self.dataPull = DataObject(dataBrought=self.dataBrought, city=self.city, name=name)
        self.restaurants = self.dataPull.data
        self.restaurants = [Restaurant(row['id'], row['name'], row['cuisine_or_amenity'].lower(), Location(row['lat'],row['long'], row['addr:postcode'], row['addr:street'], row['addr:housenumber'], ), OpenHours(row['opening_hours'])) for index, row in self.restaurants.iterrows()]
        self.distanceSorted = False
    def __getitem__(self, key):
        if hasattr(self, key):
            return getattr(self, key)
    
    def getRestaurant(self, name:str, district:str=None):
        if district:
            answer = [x for x in self.restaurants if (x.name == name and x.location.district == district)]
            if len(answer) == 1:
                return answer[0]
            else:
                return answer
        else:
            answer = [x for x in self.restaurants if x.name == name]
            if len(answer) == 1:
                return answer[0]
            else:
                return answer
            
    def getClosestList(self, address:str, n:int=5):
        for i in self.restaurants:
            try :
                if i.distanceFrom is None:
                    i.distanceFromCrow(address)
            except:
                i.distanceFromCrow(address)
        self.restaurants.sort(key=lambda x: x.distanceFrom)
        self.distanceSorted = True
        return [str(x) for x in self.restaurants[:n]]
    def getClosestViaPublicTransport(self, address:str, n:int=5):
        # for i in self.restaurants:
        #     # if i.get("distanceFrom") is None:
        #     #     print("CALCULATING DISTANCE - REMOVE LATER")
        #         i.distanceFromCrow(address)
        self.restaurants.sort(key=lambda x: x.distanceFrom)
        return [str(x) for x in self.restaurants[:n] if x.cuisine == "restaurant"]
    def restrauntListPresenter(self,rList:list):
        print("Restaurants:")
        count = 1
        for i in rList:
            print(f"{count}: - {i}")
        SubProcess = True
        while SubProcess == True:
            try:
                choice = int(input("Enter the number of the restaurant you want to see: "))
                if choice > len(rList) or choice < 1:
                    print("Invalid choice, please try again.")
                else:
                    SubProcess = False
            except ValueError:
                print("Invalid input, please enter a number.")
        return self.restaurants[choice-1]            
    def run(self):
        print("Welcome to the Restaurant Finder! (At any point press 'q' to quit.)")
        while True:
            choice = self.display_menu()
            if choice == '1':
                if self.distanceSorted == False:
                    self.getClosestList(input("Enter your address: "), 0)
                else:
                    self.restaurants.sort(key=lambda x: x.distanceFrom)
                Search = SearchQuery()
                if Search.menu() == False:
                    break
                print("Searching...")
                for i in self.restaurants:
                    i.queryScore = Search.evaluateQuery(i)
                print("Sorting...")
                # RestaurantsCopy = self.restaurants.copy()
                # RestaurantsCopy = [x for x in RestaurantsCopy if x.queryScore >= 2]
                self.restaurants.sort(key=lambda x: int(x.queryScore), reverse=True)

                print(Search)
                for i in self.restaurants[:10]:
                    print(i)
                # print([str(x) for x in self.restaurants[:10]])
            elif choice == '2':
                self.restrauntListPresenter(self.getClosestList(input("Enter your address: ")))
            elif choice == '4':
                break
            elif choice == 'q':
                print("Exiting...")
                break
            else:
                print("Invalid choice, please try again.")

    def display_menu(self):
        print("\nMENU:")
        print("1. Search Restaurants")
        print("2. Show closest restaurants")
        print("4. Exit")
        return input("Enter choice: ")
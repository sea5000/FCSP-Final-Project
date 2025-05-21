from abc import ABC, abstractmethod
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
from pathvalidate import is_valid_filename
from prettytable import PrettyTable

weekdayMap = {
    r'\b(Mon|Montag|Mo)\b': 'Mo',
    r'\b(Tue|Tues|Dienstag|Di)\b': 'Tu',
    r'\b(Wed|Mittwoch|Mi)\b': 'We',
    r'\b(Thu|Thur|Donnerstag|Do)\b': 'Th',
    r'\b(Fri|Freitag|Fr)\b': 'Fr',
    r'\b(Sat|Samstag|Sa)\b': 'Sa',
    r'\b(Sun|Sonntag|So)\b': 'Su',
}
def normalizeWeekdays(text):
    for pattern, replacement in weekdayMap.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text
def ParseHours(inputString):
    def dayCheck(inpt:str,dayMap,gDayMap):
        if inpt in dayMap:
            return dayMap
        elif inpt in gDayMap:
            return gDayMap
        else:
            return None
    dayMap = ["Mo","Tu","We","Th","Fr","Sa","Su","PH"]
    gDayMap = ["Mo","Di","Mi","Do","Fr","Sa","So","PH"]
    NormalDayMap = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun","PH"]
    patternDays = re.compile(r'((?:PH|Mo|Tu|We|Th|Fr|Sa|Su)|(?:PH|Mo|Do|Mi|Di|Fr|Sa|So))')
    patternDayRange = re.compile(r'((?:[A-Z]{1}[a-z]{1}\-[A-Z]{1}[a-z]{1})+(?![A-z]|[^ \-\,]))')
    patternSubDay = re.compile(r'((?:(?:[A-Z]{1}(?:[a-z]{1}|[A-Z]{1})+\-*\,*\ *)*,*\W*)(?:[\ *\,*]*\d{2}:\d{2}-\d{2}:\d{2}|\d{2}:\d{2} - \d{2}:\d{2}|off|OFF)+)')
    patternDaysOff = re.compile(r'([(PH|Mo|Tu|We|Th|Fr|Sa|Su)\,\-]+) (?:off|closed)')
    patternMonthRange = re.compile(r'(?:[A-Z][a-z]{2}(?:-[A-Z][a-z]{2})?)')#(?:(?:[A-Z]{1}[a-z]{2}\-[A-Z]{1}[a-z]{2})|(?:[A-Z]{1}[a-z]{2}(?<=[\,\ ]{0,1})(?=[\,\ ]*)))
    patternMonth = re.compile(r'((?:[A-Z]{1}[a-z]{2})+)')
    patternHours = re.compile(r'(\d{2}:\d{2}-\d{2}:\d{2})')
    monthRange = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    schedule = {}
    
    #This will replace any 3 letter days with 2 letter, german or english.
    inputString = normalizeWeekdays(inputString)
    rePatternSubDay = patternSubDay.findall(inputString)
    # print(rePatternSubDay)
    monthB = False
    if rePatternSubDay == []: #If there is no return from the regex for sub day schedules
        return schedule
    else:
        for item in rePatternSubDay:
            reMonthRange = patternMonthRange.findall(item)
            if reMonthRange != [] or any([True for i in monthRange if i in item]): #Looks for if there is a month range or month in the item, or a month in the item.
                if monthB == False: # Establishes the schedule but by month. 
                    _ = schedule.copy()
                    schedule.clear()
                    for month in monthRange:
                        schedule[month] = _.copy()
                if reMonthRange != []: #This handles ranges of months ie. Jul-Aug Su 07:00-18:00
                    for monthSpan in reMonthRange:
                        if "-" in monthSpan:
                            mStart, mEnd = monthSpan.split("-")
                            reDayRange  = patternDayRange.findall(item)
                            reDays = patternDays.findall(item)
                            reHours = patternHours.findall(item)
                            for month in monthRange[monthRange.index(mStart):monthRange.index(mEnd)+1]:
                                # print(month)
                                if "off" in item:
                                    for day in reDays:
                                        schedule[month][NormalDayMap[dayCheck(day,dayMap,gDayMap).index(day)]] = ["OFF"]
                                elif reDayRange != []:
                                    for day in reDayRange:
                                        start, end = day.split("-")
                                        for nday in NormalDayMap[dayCheck(start,dayMap,gDayMap).index(start):dayCheck(end,dayMap,gDayMap).index(end)+1]:
                                            schedule[month][nday] = reHours
                                elif reDays != []:
                                    for day in reDays:
                                        schedule[month][NormalDayMap[dayCheck(day,dayMap,gDayMap).index(day)]] = reHours
                                elif reHours != []:
                                    for day in NormalDayMap:
                                        schedule[month][day] = reHours
                                else:
                                    raise ValueError(f"Uncaught date: '{inputString}' item: '{item}'")
                        else:
                            reDayRange  = patternDayRange.findall(item)
                            reDays = patternDays.findall(item)
                            reHours = patternHours.findall(item)
                            month = monthSpan
                            if "off" in item:
                                for day in reDays:
                                    schedule[month][NormalDayMap[dayCheck(day,dayMap,gDayMap).index(day)]] = ["OFF"]
                            elif reDayRange != []:
                                for day in reDayRange:
                                    start, end = day.split("-")
                                    for nday in NormalDayMap[dayCheck(start,dayMap,gDayMap).index(start):dayCheck(end,dayMap,gDayMap).index(end)+1]:
                                        schedule[month][nday] = reHours
                            elif reDays != []:
                                for day in reDays:
                                    schedule[month][NormalDayMap[dayCheck(day,dayMap,gDayMap).index(day)]] = reHours
                            elif reHours != []:
                                for day in NormalDayMap:
                                    schedule[month][day] = reHours
                            else:
                                raise ValueError(f"Uncaught date: '{inputString}' item: '{item}'")
                    monthB = True
                else: #Else if there is no month range, then it is just a single month.
                    reDayRange  = patternDayRange.findall(item)
                    months = patternMonth.findall(item)
                    reDays = patternDays.findall(item)
                    reHours = patternHours.findall(item)
                    for month in months:
                        if "off" in item:
                            for day in reDays:
                                schedule[month][NormalDayMap[dayCheck(day,dayMap,gDayMap).index(i)]] = ["OFF"]
                        elif reDayRange != []: #a range of days
                            for i in reDayRange:
                                start, end = i.split("-")
                                for day in NormalDayMap[dayCheck(start,dayMap,gDayMap).index(start):dayCheck(end,dayMap,gDayMap).index(end)+1]:
                                    schedule[month][day] = reHours
                        elif reDays != []:
                            for day in reDays:
                                schedule[month][NormalDayMap[dayCheck(day,dayMap,gDayMap).index(i)]] = reHours
                        elif reDays == [] and reHours != []:
                            for day in reDays:
                                schedule[month][NormalDayMap[dayCheck(day,dayMap,gDayMap).index(i)]] = reHours
                        elif reHours != [] and reDays == []: #All else
                            for day in NormalDayMap:
                                schedule[month][NormalDayMap[dayCheck(day,dayMap,gDayMap).index(i)]] = reHours
                        else:
                            raise ValueError(f"Uncaught date: '{inputString}' item: '{item}'")
                    monthB = True
                continue
            if monthB == True and len(schedule)>7:
                # print("Schedule:",schedule)
                reHours = patternHours.findall(item)
                reDayRange = patternDayRange.findall(item)
                reMonthSpan = patternMonthRange.findall(item)
                if reMonthSpan != []:
                    if "off" in item:
                        reOffDays = patternDaysOff.findall(item)
                        for month,week in schedule.items():
                            for day in reOffDays:
                                schedule[month][day] = ["OFF"]
                    elif reDayRange != []: #a range of days
                        for month,week in schedule.items():
                            for i in reDayRange:
                                start, end = i.split("-")
                                for day in NormalDayMap[dayCheck(start,dayMap,gDayMap).index(start):dayCheck(end,dayMap,gDayMap).index(end)+1]:
                                    schedule[month][day] = patternHours.findall(item)
                    elif reDays == [] and patternHours.findall(item) != []: # if it is just Hours then...
                        for month,week in schedule.items():
                            for day in week:
                                schedule[month][day] = reHours
                    else: #All else, if it is just a day and a time.
                        for i in reDays:
                            schedule[month][NormalDayMap[dayCheck(i,dayMap,gDayMap).index(i)]] = patternHours.findall(item)
                else:
                    reHours = patternHours.findall(item)
                    reDays = patternDays.findall(item)
                    if "off" in item and reHours == []:
                        reHours = ["OFF"]
                    for month,week in schedule.items():
                        for day in reDays:
                            schedule[month][NormalDayMap[dayCheck(day,dayMap,gDayMap).index(day)]] = reHours
                # raise ValueError(f"Data after Month {item} in {inputString}")
                # return schedule
                continue
            reDayRange  = patternDayRange.findall(item)
            # print(reDayRange)
            if "OFF" in item or "off" in item:
                daysOff = patternDaysOff.findall(item)
                reDaysRange = patternDayRange.findall(item)
                if daysOff == []:
                    return schedule
                elif reDaysRange != []:
                    for i in reDaysRange:
                        start, end = i.split("-")
                        for day in NormalDayMap[dayCheck(start,dayMap,gDayMap).index(start):dayCheck(end,dayMap,gDayMap).index(end)+1]:
                            schedule[day] = ["OFF"]
                else:
                    daysOff = patternDays.findall(item)
                    for i in daysOff:
                        schedule[NormalDayMap[dayCheck(i,dayMap,gDayMap).index(i)]] = ["OFF"]
            elif reDayRange != []:
                # print(reDayRange)
                for i in reDayRange:
                    # print(i)
                    start, end = i.split("-")
                    # print(start,end)
                    # print(dayCheck(start,dayMap,gDayMap),dayCheck(end,dayMap,gDayMap))
                    for day in NormalDayMap[dayCheck(start,dayMap,gDayMap).index(start):dayCheck(end,dayMap,gDayMap).index(end)+1]:
                        schedule[day] = patternHours.findall(item)
            else:
                reDays = patternDays.findall(item)
                if reDays == []:
                    for day in NormalDayMap:
                        schedule[day] = patternHours.findall(item)
                else:
                    for day in reDays:
                        schedule[NormalDayMap[dayCheck(day,dayMap,gDayMap).index(day)]] = patternHours.findall(item)
    return schedule


class DataObject:
    def __init__(self, dataBrought:bool=True, city:str="Währing, Wien, Austria", name:str=None):
        self.city:str = city
        self.dataBrought:bool = dataBrought
        self.name:str = name
        if dataBrought:
            self.addData(name)
        else:
            self.dataPull(self.city,name=name)
    def dataPull(self, city:str="Währing, Wien, Austria",name:str=None,populateAddress:bool=True): # Data Pull Object, establishes the parameters for the pull and pulls data from OSM.
        print(f"Initializing DataPull... {self.city}")
        self.restaurants = []
        
        tags = {'amenity': ['restaurant', 'pub', 'cafe', 'fast_food', 'bar', 'food_court', 'biergarten', 'ice_cream']}
        # tags is the list of amenity we are looking for. (Filters off other OSM items.)
        print("Pulling Data from OSM...")
        restaurants = ox.features_from_place(self.city, tags) #Pulls data

        # def get_cuisine_or_amenity(row):
        #     if row['amenity'] == 'restaurant' and pd.notna(row['cuisine']):
        #         return row['cuisine']
        #     else:
        #         return row['amenity']
            
        # restaurants['cuisine_or_amenity'] = restaurants.apply(get_cuisine_or_amenity, axis=1)

        # geolocator = Nominatim(user_agent="my_geocoder")
        # geocode = RateLimiter(geolocator.reverse, min_delay_seconds=1)
        
        restaurants['id'] = [i[1] for i in restaurants.index]#Sets the ID for the restraunt form the index to the id column
        restaurants["lat"] = restaurants['geometry'].apply(lambda x: re.search(r'(\d+[.]{1}\d+[ ]\d+[.]{1}\d+)', str(x)).group(0).split(" ")[0]) # Grabs the lat coord from the geometry field.
        restaurants["long"] = restaurants['geometry'].apply(lambda x: re.search(r'(\d+[.]{1}\d+[ ]\d+[.]{1}\d+)', str(x)).group(0).split(" ")[1]) # Grabs the long coord from the geometry field.
        restaurants = restaurants.drop(columns=['geometry']) # Removes teh now redundant geometry field.

        if populateAddress: # If this is true (default it is) this will populate addressess based of the lat and long. Although there is good data in OSM, I opted for losing some accuracy in the address and having a complete address dataset.
            print("Getting Addresses...")
            start_time = time.time()
            for index, row in restaurants.iterrows():
                lat = row['lat']
                long = row['long']
                crs_wgs84 = CRS("EPSG:4326")
                crs_epsg31256 = CRS("EPSG:31256")
                transformer = Transformer.from_crs(crs_wgs84, crs_epsg31256, always_xy=True) # Converts Coordinate systems, from lat long, to vienna's own coordinate system, allows us to query their database for addresses.
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
                    
        self.dataPull = restaurants.dropna(subset=['name'])  #Removes rows without this column field.
        #[['id', 'name', 'lat', 'long', 'addr:street', 'addr:housenumber', 'addr:city', 'addr:postcode', "cuisine_or_amenity","opening_hours"]]
        print(self.dataPull.head())
        print("Data Pulled. Writing...")
        self.writeToCSV(name=name)
        return self.dataPull
    def addData(self, CSVName:str=None):
        if CSVName is None or CSVName == "":
            raise ValueError("CSVName cannot be None")
        if ".csv" in CSVName:
            CSVName = CSVName.rstrip(".csv")
        if is_valid_filename(CSVName) == False:
            raise ValueError("CSVName is not a valid filename")
        try:
            df = pd.read_csv(CSVName+".csv", encoding="utf-8-sig")
        except:
            raise FileNotFoundError(f"File {CSVName} not found")
        self.dataPull=df
        print(f"Data added from {CSVName}")
        print("====================")
    
    def writeToCSV(self,name:str=None):

        if name is None:
            name = self.city.replace(",","").replace(" ","_")
        self.dataPull.to_csv(f"{name}.csv", encoding="utf-8-sig",index=False)
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
    def __init__(self, id, name, cuisine, location:Location, hours:OpenHours, **kwargs):
        self.id = id
        self.name = name
        self.cuisine = cuisine
        self.hours = hours
        self.location = location
        for i in kwargs:
            exec(f"self.{i} = {kwargs[i]}")
    def __getitem__(self, key):
        if hasattr(self, key):
            return getattr(self, key)
        if self.hours and self.hours.hours:
            return self.hours.hours.get(key)
        raise KeyError(f"{key} not found in Restaurant or DataBase")
    def __str__(self):
        queryScore = getattr(self, "queryScore", None)
        if self.distanceFrom < 1:
            distance = str(int(round(self.distanceFrom,3)*1000)) +" m"
        else:
            distance = str(round(self.distanceFrom,2)) + " km"
        return f"{self.id} - {self.name} ({self.cuisine}) - {self.location} - {distance}" + (f" - {self.queryScore} points" if queryScore is not None else "")

    def distanceFromCrow(self, userPoint):
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
        now = dt.datetime.now()
        currentDay = now.strftime("%a")  # e.g. "Mon"
        currentTime = now.time()  # datetime.time object directly
        currentMonth = now.strftime("%b")  # e.g. "Apr"
        if self.hours.hours is None:
            return "No Data"
        if len(self.hours.hours) > 8:
            if currentMonth not in self.hours.hours:
                # print(f"{currentMonth} not in self.hours.hours: {self.hours.hours.keys()}")
                return False
            hourInfo = self.hours.hours[currentMonth]
            if hourInfo == {} or hourInfo.get(currentDay) == None:
                return False
            hours = hourInfo[currentDay]
        else:
            if currentDay not in self.hours.hours:
                return False
            hours = self.hours.hours[currentDay]
            if hours == [] or hours == {}:
                return False
        for i in hours:
            if i == "OFF":
                return False
            start, end = i.split("-")
            if start == "24:00":
                start = "23:59"
            if end == "24:00":
                end = "23:59"
            if int(end[:2]) > 23:
                end = f"{int(end[:2]) - 24:02}:{end[-2:]}"
            start_time = dt.datetime.strptime(start, "%H:%M").time()
            end_time = dt.datetime.strptime(end, "%H:%M").time()
            if start_time <= currentTime <= end_time:
                return True
        return False
    def selector(self):
        status = True
        while status == True:
            try:
                count = 1
                for k,i in self.__dict__.items():
                    print(f"{count}: {k}")
                    count +=1
                choice = input("Enter your selection: ")
                match choice:
                    case choice if choice == "q" or choice == "Q":
                        return "q"
                    case choice if choice == "m" or choice == "M":
                        return "m"
                    case choice if choice == "":
                        print("No choice made, please try again.")
                    case choice if int(choice) > count:
                        print("Invalid choice, please try again. Or press 'm' to return to the menu.")
                    case choice if int(choice) < len(self.__dict__.keys() or choice > len(self.__dict__.keys())):
                        print("Invalid choice, please try again")
                    case _:
                        print(self.__dict__[list(self.__dict__.keys())[int(choice)-1]])
                        print("===================")
            except:
                return "q"

class SearchQuery:
    def __init__(self, cuisine:str=None, Diststance:int=None, District:str=None, OpenNow:bool=False):
        self.cuisine = cuisine
        self.Diststance = Diststance
        self.District = District
        self.OpenNow = OpenNow
    def __str__(self):
        distance = getattr(self, "Distance", None)
        if distance == None:
            return f"Looking for {self.cuisine} {"that is open now" if self.OpenNow == True else "that is not open now"}"
        else:
            return f"Looking for {self.cuisine} within {self.Diststance}km of the user {"that is open now" if self.OpenNow == True else "that is not open now"}"
    def setQueryParameters(self, cuisine:str=None, Diststance:int=None, District:str=None, OpenNow:bool=False):
        self.cuisine = cuisine
        self.Diststance = Diststance
        self.District = District
        self.OpenNow = OpenNow
        return [self.query, self.cuisine, self.location, self.hours]
    def menu(self):
        instructions = set()
        print("===================")
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
                self.OpenNow = True
            else:
                self.OpenNow = False
    def evaluateQuery(self, restaurant:Restaurant):
        if self.District == restaurant.location.district:
            print(self.District,restaurant.location.district)
        score = 0
        if self.cuisine is not None and self.cuisine in restaurant.cuisine:
            score += 1
        if self.Diststance is not None and restaurant.distanceFrom < self.Diststance:
            score += 1
        if self.District is not None and str(restaurant.location.district) == str(self.District):
            # print("DISTRICT CHECK")
            score += 1
        if self.OpenNow and restaurant.isCurrentlyOpen() == True:
            score += 1
        return score
            
class DataBase(DataObject):
    def __init__(self, city:str="Währing, Wien, Austria", name:str=None, dataBrought:bool=True):
        super().__init__(dataBrought=dataBrought, city=city, name=name)
        #self.dataPull = DataObject(dataBrought=self.dataBrought, city=self.city, name=name)
        #self.city = city
        self.restaurants = []
        #self.dataBrought = dataBrought
        #self.data = self.dataPull.data
        self.cuisines = set()
        for index, row in self.dataPull.iterrows():
            id = row['id']
            name = row['name']
            cuisine = row['cuisine_or_amenity']
            if ";" in cuisine:
                cuisine = cuisine.split(";")
            elif "," in cuisine:
                cuisine = cuisine.split(",")
            else:
                cuisine = [cuisine]
            for i in cuisine:
                self.cuisines.add(i)
            lat = row['lat']
            long = row['long']
            city = row['addr:city']
            street = row['addr:street']
            house = row['addr:housenumber']
            district = row['addr:postcode']
            hours = row['opening_hours']
            location = Location(lat, long, district, street, house)
            hours = OpenHours(hours)
            row = row.drop(columns=['id','name','cuisine_or_amenity','lat','long','addr:city','addr:street','addr:housenumber','addr:postcode','opening_hours'])
            self.restaurants.append(Restaurant(id, name, cuisine, location, hours))
            # self.restaurants = Restaurant(row['id'], row['name'], row['cuisine_or_amenity'].lower(), Location(row['lat'],row['long'], row['addr:postcode'], row['addr:street'], row['addr:housenumber'])
        # self.restaurants = [Restaurant(row['id'], row['name'], row['cuisine_or_amenity'].lower(), Location(row['lat'],row['long'], row['addr:postcode'], row['addr:street'], row['addr:housenumber'], ), OpenHours(row['opening_hours']),) for index, row in self.restaurants.iterrows()]
        self.distanceSorted = False
        self.cuisines = list(self.cuisines).sort()
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
    def getClosestList(self):
        for i in self.restaurants:
            try :
                if i.distanceFrom is None:
                    i.distanceFromCrow(self.addressCoords)
            except:
                i.distanceFromCrow(self.addressCoords)
        self.restaurants.sort(key=lambda x: x.distanceFrom)
        self.distanceSorted = True
        return True
    def getClosestViaPublicTransport(self, address:str, n:int=5):
        ...
        # for i in self.restaurants:
        #     # if i.get("distanceFrom") is None:
        #     #     print("CALCULATING DISTANCE - REMOVE LATER")
        #         i.distanceFromCrow(address)
        self.restaurants.sort(key=lambda x: x.distanceFrom)
        return [str(x) for x in self.restaurants[:n] if x.cuisine == "restaurant"]
    def usrGetCoords(self, address:str):
        try:
            self.addressCoords = ox.geocoder.geocode(address)
            return True
        except ox._errors.InsufficientResponseError  as e:
            print(f"Caught an InsufficientResponseError: {e}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return False

    def restrauntListPresenter(self, n:int=10):
        print("===================")
        print("Restaurants:")
        SubProcess = True
        while SubProcess == True:
            try:
                count = 1
                table = PrettyTable()
                table.field_names = ["#", "ID", "Name", "Cuisine", "Location", "Distance", "Search Score"]
                
                
                for r in self.restaurants[:n]:
                    queryScore = getattr(r, "queryScore", None)
                    if r['distanceFrom'] < 1:
                        distance = str(int(round(r['distanceFrom'],3)*1000)) +" m"
                    else:
                        distance = str(round(r['distanceFrom'],2)) + " km"
                    table.add_row([count, r['id'], r['name'], r['cuisine'], r['location'], distance, f"{r['queryScore']} points" if queryScore is not None else ""])
                    #print(f"{count}: - {i}")
                    count+=1
                print(table)
                print("===================")
                choice = input("Press 'q' to quit or 'm' to return to the menu\nEnter the number of the restaurant you want to see: ")
                if choice == "q":
                    return "q"
                    SubProcess = False
                elif choice == "m":
                    return "m"
                    SubProcess = False
                else:
                    choice = int(choice)
                match choice:
                    case choice if choice <= 1 or choice >= len(self.restaurants):
                        print(f"Choice '{choice}' is out of range of list, please try again.")
                    case choice if type(choice) != int:
                        print(f"Choice '{choice}' is not an integer, please try again.")
                    case _:
                        value = self.restaurants[choice-1].selector()
                        if value == "q":
                            raise EnvironmentError("Quit pressed")
                        if value == "m":
                            raise EnvironmentError("Return to menu pressed")
            except ValueError:
                print("Invalid input, please enter a number.")
                continue
            except EnvironmentError as e:
                if str(e) == "Return to menu pressed":
                    continue
                elif str(e) == "Quit pressed":
                    return "q"
                else:
                    print("Invalid, try again or exit with 'q' or 'm'.")
                    continue
        return self.restaurants[choice-1]         

    def checkUserAddr(self):
        if self.distanceSorted == False:
            goodResp = False
            while goodResp == False:
                self.inpUsrAddress = input("Enter your address: ")
                if self.inpUsrAddress == 'q':
                    return "q"
                elif self.inpUsrAddress == 'm':
                    return "m"
                goodResp = self.usrGetCoords(self.inpUsrAddress)
            lat = self.addressCoords[1]
            long = self.addressCoords[0]
            self.usrAddress = {}
            crs_wgs84 = CRS("EPSG:4326")
            crs_epsg31256 = CRS("EPSG:31256")
            transformer = Transformer.from_crs(crs_wgs84, crs_epsg31256, always_xy=True) # Converts Coordinate systems, from lat long, to vienna's own coordinate system, allows us to query their database for addresses.
            easting, northing = transformer.transform(lat, long)
            url = f"https://data.wien.gv.at/daten/OGDAddressService.svc/ReverseGeocode?location={easting},{northing}&crs=EPSG:31256&type=A3:8012"
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = json.loads(response.text)
                    self.usrAddress['addr:street'] = data['features'][0]['properties']['StreetName']
                    self.usrAddress['addr:housenumber'] = data['features'][0]['properties']['StreetNumber']
                    self.usrAddress['addr:city'] = data['features'][0]['properties']['Municipality']
                    self.usrAddress['addr:postcode'] = data['features'][0]['properties']['PostalCode']
            except:
                raise SystemError(response.status_code)
            self.getClosestList()
    def breakInput(self, inpt):
        if inpt == "q":
            return True
        elif inpt== "m":
            return "m"
        else:
            return False
        
    def run(self):
        print("Welcome to the Restaurant Finder!\n(At any point press 'q' to quit or 'm' to return to the menu.)")
        inpt = False
        while self.breakInput(inpt) == False:
            choice = self.display_menu()
            if choice == '1':
                resp = self.checkUserAddr()
                if resp == 'q':
                    inpt = resp
                    break
                if resp == 'm':
                    inpt == resp
                    break
                Search = SearchQuery()
                if Search.menu() == False:
                    breakOut = True
                print("Searching...")
                for i in self.restaurants:
                    i.queryScore = Search.evaluateQuery(i)
                print("Sorting...")
                # RestaurantsCopy = self.restaurants.copy()
                # RestaurantsCopy = [x for x in RestaurantsCopy if x.queryScore >= 2]
                self.restaurants.sort(key=lambda x: int(x.queryScore), reverse=True)

                print(Search)
                resp = self.restrauntListPresenter()
                if resp == "q":
                    inpt = resp
                    break
                if resp == "m":
                    inpt = resp
                    break
                # print([str(x) for x in self.restaurants[:10]])
            elif choice == '2':
                resp = self.checkUserAddr()
                if resp == 'q':
                    inpt = val
                if resp == 'm':
                    inpt = val
                resp = self.restrauntListPresenter()
                if resp == "q":
                    inpt = resp
                    break
                if resp == "m":
                    inpt = resp
                    break
            elif choice == "3":
                for i in self.cuisines:
                    print(i)
            elif choice == '4':
                self.distanceSorted = False
                resp = self.checkUserAddr()
                print(resp)
                if resp == 'q':
                    inpt = resp
                    break
                if resp == 'm':
                    inpt = resp
                    break
                print(f"Address '{self.inpUsrAddress}' was normalized to '{str(self.usrAddress['addr:street']+" "+self.usrAddress['addr:housenumber']+", "+self.usrAddress['addr:postcode']+" "+self.usrAddress['addr:city'])}' at '{self.addressCoords}'")
            elif choice == 'q':
                print("Exiting...")
                breakOut = True
            else:
                print("Invalid choice, please try again.")
        if inpt == 'm':
            inpt = False
            self.run()
    
    def display_menu(self):
        print("\nMENU:")
        print("1. Search Restaurants")
        print("2. Show closest restaurants")
        print("3. Show all Cuisines")
        print("4. Set User Location")
        print("5. Search Options")
        print("6. Exit")
        return input("Enter choice: ")
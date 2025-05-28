from abc import ABC, abstractmethod
import osmnx as ox
import pandas as pd
from tqdm import tqdm
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
import json

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
def getInput(prompt:str) ->str:
        inp = input(prompt)
        if inp.lower() == "q":
            raise MenuBreak("q")
        elif inp.lower() == "m":
            raise MenuBreak("m")
        return inp
def getSecond(dict:dict,term1:str,term2:str,fun=None):
    _x = dict.get(term1)
    if _x != None and not isinstance(_x, str):
        if _x.get(term2) != None:
            if fun != None:
                return fun(_x.get(term2))
            else:
                return _x.get(term2)
        else:
            return None
    else:
        return None

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
        try:
            sampleDf = pd.read_csv(CSVName+".csv", nrows=100)
            dtypeMap = {col: str for col in sampleDf.columns}
            self.dataPull = pd.read_csv(CSVName+".csv",dtype=dtypeMap, encoding="utf-8-sig") #, low_memory=False
        except FileNotFoundError:
            raise FileNotFoundError(f"File {CSVName} not found")
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
        return f"{self.street} {self.house}, {self.district} - ({self.lat},{self.long})"

class OpenHours:
    def __init__(self, hours:str|None):
        if hours == None:
            self.hours = None
        else:
            hours = re.sub(r'(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})', r'\1-\2', hours)
            self.hours = ParseHours(hours)
    def __str__(self):
        return str(self.hours)
    def __getitem__(self, key):
        return self.hours.get(key) if self.hours else None

class DataEntity(ABC):
    @abstractmethod
    def matches(self, criteria: dict[str, any]) -> bool:
        ...
    @abstractmethod
    def get_field(self, field_name: str):
        ...
    @abstractmethod
    def distanceFromCrow(self, userPoint: tuple):
        ...
class Restaurant(DataEntity):
    def __init__(self, data:dict):
        self.name = data['identity']['name']
        self.amenity = data['identity']['amenity']
        self.id = data['identity']['id']
        self.hours = getSecond(data,'opHoursAttr','opening_hours',OpenHours)
        lat, long, district, street, housenumber = data['locationAttr']['lat'],data['locationAttr']['long'],data['locationAttr']['addr:postcode'],data['locationAttr']['addr:street'],getSecond(data,'locationAttr','addr:housenumber')
        self.location = Location(lat, long, district, street, ("" if housenumber == None else housenumber)) #lat, long, district, street, house
        for k,i in data.items():
            setattr(self,k,i)
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
    def matches(self, criteria: dict[str, any]) -> bool:
        """Polymorphic implementation for Restaurant"""
        phoneList = ["phone","contact:phone","contact:mobile","phone:mobile"]
        for key, value in criteria.items():
            veg = (True if getSecond(self.__dict__, 'menuCuisineAttr',"diet:vegetarian") == "yes" else False)
            wheelchair = (True if getSecond(self.__dict__,'accessibilityAttr','wheelchair') == 'yes' else False)
            outdoor = (True if getSecond(self.__dict__,'servicesAttr','outdoor_seating') == 'yes' else False)
            delivery = (True if getSecond(self.__dict__,'servicesAttr','delivery') == "yes" else False)
            phone = getSecond(self.__dict__,"onlineContactAttr","phone")
            phone = {} if phone == None else phone
            if key == "district" and self.location.district != value:
                return False
            elif key == "distance" and self.distanceFrom < value: # Should return true if distance is shorter than the value
                return False
            elif key == "open" and self.isCurrentlyOpen() == value:
                return False
            elif key == "vegitarian" and veg != None and veg.lower() != value:
                return False
            elif key == "wheelchair" and wheelchair != None and wheelchair != value:
                return False
            elif key == "cuisine" and self.cuisine != value:
                return False
            elif key == "chain" and self.chain != None and self.chain != value:
                return False
            elif key == "outdoor_seating" and outdoor != None and outdoor != value:
                return False
            elif key == "delivery" and delivery != None and delivery != value:
                return False
            elif key == "phone" and phone != None and value == False and any([True for k,i in phone.items() if i in phoneList]):
                return False
            elif key == "phone" and phone != None and value == True and any([False if i in phoneList else True for k,i in phone.items()]):
                return False
        return True
    def get_field(self, field_name):
        if hasattr(self, field_name):
            return getattr(self, field_name)
        return None
    def distanceFromCrow(self, userPoint):
        try:
            resPoint = Point(float(self.location.lat), float(self.location.long))
            self.distanceFrom = geodesic((userPoint[0], userPoint[1]), (resPoint.y, resPoint.x)).kilometers
        except:
            print(self.name,self.location['lat'],self.location['long'])
        return self.distanceFrom
    def distanceFromPT(self, address):
        ...
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
            count = 1
            for k,i in self.__dict__.items():
                print(f"{count}: {k}")
                count +=1
            choice = getInput("Enter your selection: ")
            match choice:
                case choice if choice == "":
                    print("No choice made, please try again.")
                case choice if int(choice) > count:
                    print("Invalid choice, please try again. Or press 'm' to return to the menu.")
                case choice if int(choice) > len(self.__dict__.keys() or choice < 1):
                    print("Invalid choice, please try again")
                case _:
                    print(self.__dict__[list(self.__dict__.keys())[int(choice)-1]])
                    print("===================")
#['restaurant', 'pub', 'cafe', 'fast_food', 'bar', 'food_court', 'biergarten', 'ice_cream']
class Chain(DataEntity):
    def __init__(self, data:dict):
        self.name = data['identity']['name']
        self.amenity = data['identity']['amenity']
        self.id = data['identity']['id']
        self.hours = getSecond(data,'opHoursAttr','opening_hours',OpenHours)
        self.chain = getSecond(data,'operatorAttr','brand')
        lat, long, district, street, housenumber = data['locationAttr']['lat'],data['locationAttr']['long'],data['locationAttr']['addr:postcode'],data['locationAttr']['addr:street'],getSecond(data,'locationAttr','addr:housenumber')
        self.location = Location(lat, long, district, street, ("" if housenumber == None else housenumber)) #lat, long, district, street, house
        for k,i in data.items():
            setattr(self,k,i)
    def matches(self, criteria: dict[str, any]) -> bool:
        """Polymorphic implementation for Restaurant"""
        phoneList = ["phone","contact:phone","contact:mobile","phone:mobile"]
        for key, value in criteria.items():
            veg = (True if getSecond(self.__dict__, 'menuCuisineAttr',"diet:vegetarian") == "yes" else False)
            wheelchair = (True if getSecond(self.__dict__,'accessibilityAttr','wheelchair') == 'yes' else False)
            outdoor = (True if getSecond(self.__dict__,'servicesAttr','outdoor_seating') == 'yes' else False)
            delivery = (True if getSecond(self.__dict__,'servicesAttr','delivery') == "yes" else False)
            phone = getSecond(self.__dict__,"onlineContactAttr","phone")
            phone = {} if phone == None else phone
            if key == "district" and self.location.district != value:
                return False
            elif key == "distance" and self.distanceFrom < value: # Should return true if distance is shorter than the value
                return False
            elif key == "open" and self.isCurrentlyOpen() == value:
                return False
            elif key == "vegitarian" and veg != None and veg.lower() != value:
                return False
            elif key == "wheelchair" and wheelchair != None and wheelchair != value:
                return False
            elif key == "cuisine" and self.cuisine != value:
                return False
            elif key == "chain" and self.chain != None and self.chain != value:
                return False
            elif key == "outdoor_seating" and outdoor != None and outdoor != value:
                return False
            elif key == "delivery" and delivery != None and delivery != value:
                return False
            elif key == "phone" and phone != None and value == False and any([True for k,i in phone.items() if i in phoneList]):
                return False
            elif key == "phone" and phone != None and value == True and any([False if i in phoneList else True for k,i in phone.items()]):
                return False
        return True
    def get_field(self, field_name):
        if hasattr(self, field_name):
            return getattr(self, field_name)
        return None
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
            count = 1
            for k,i in self.__dict__.items():
                print(f"{count}: {k}")
                count +=1
            choice = getInput("Enter your selection: ")
            match choice:
                case choice if choice == "":
                    print("No choice made, please try again.")
                case choice if int(choice) > count:
                    print("Invalid choice, please try again. Or press 'm' to return to the menu.")
                case choice if int(choice) > len(self.__dict__.keys() or choice < 1):
                    print("Invalid choice, please try again")
                case _:
                    print(self.__dict__[list(self.__dict__.keys())[int(choice)-1]])
                    print("===================")
    def __str__(self):
        queryScore = getattr(self, "queryScore", None)
        if self.distanceFrom < 1:
            distance = str(int(round(self.distanceFrom,3)*1000)) +" m"
        else:
            distance = str(round(self.distanceFrom,2)) + " km"
        return f"{self.id} - {self.name} ({self.cuisine}) - {self.location} - {distance}" + (f" - {self.queryScore} points" if queryScore is not None else "")
    def __repr__(self):
        return f"{self.name} - {type(self)} - {self.location}"
    def distanceFromCrow(self, userPoint):
        try:
            resPoint = Point(float(self.location.lat), float(self.location.long))
            self.distanceFrom = geodesic((userPoint[0], userPoint[1]), (resPoint.y, resPoint.x)).kilometers
        except:
            print(self.name,self.location.lat,self.location.long)
        return self.distanceFrom
class SearchQuery:  
    def __init__(self, cuisine:str=None, Diststance:int=None, District:str=None, OpenNow:bool=False):
        self.cuisine = cuisine
        self.Diststance = Diststance
        self.District = District
        self.OpenNow = OpenNow
        self.parameter = {}
    def __str__(self):
        distance = getattr(self, "Distance", None)
        if distance == None:
            return f"Looking for {self.cuisine} {"that is open now" if self.OpenNow == True else "that is not open now"}"
        else:
            return f"Looking for {self.cuisine} within {self.Diststance}km of the user {"that is open now" if self.OpenNow == True else "that is not open now"}"
    def menu(self)->bool:
        instructions = set()
        print("===================")
        print("Select your search parameters:")
        print("1. Cuisine")
        print("2. Distance")
        print("3. District")
        print("4. Open Now")
        print("5. Done")
        print("Enter any combination of the above choice (ie 143 or 1,3,2).")
        """elif "and" in choice and "or" in choice
        elif "and" in choice:
            choice = choice.lower.split("and")
            for i in choice:
                instructions.add(i)"""
        choice = getInput("Enter: ")
        if choice == '5':
            return False
        elif choice == '':
            print("No choice made, please try again.")
            return True
        elif ',' in choice:
            choice = choice.split(",")
            for i in choice:
                instructions.add(int(i))
        elif choice.isdigit():
            choice = [int(i) for i in choice]
            for i in choice:
                instructions.add(int(i))
        else:
            print("Invalid choice, please try again")
            return True
        for i in instructions:
            if i == 1:
                print("Input any number of cuisines to be 'OR' searched. (i.e. 'thai or sushi')")
                _ = getInput("Enter cuisine: ")
                self.parameter['cuisne':[]]#######
                self.cuisine = _
            elif i == 2:
                _ = getInput("Enter distance (km): ")
                self.Diststance = float(_)
            elif i ==   3:
                _ = getInput("Enter district: ")
                self.District = str(int(_))
                # print(self.District)
            elif i == 4:
                self.OpenNow = True
            else:
                self.OpenNow = False
    def sort(self,sortOptions:list[int],data:list):
        dataC = {}
        for i in sortOptions:
            dataC[i] = data.copy()
            if i == "1":
                self.sortBubble(data)
            elif i == "2":
                self.sortInsert(data)

    def search(self,searchOptions:list[int],data:list):
        ...
        dataC = {}
        for i in searchOptions:
            dataC[i] = data.copy()
            if i == "1":
                dataC[i] = self.linearSearch(data)
            elif i == "2":
                dataC[i] = self.linearSearch(data)
        return dataC#searchOptions[0]}
    def linearSearch(self,arr, target):
        for i in range(len(arr)):
            if arr[i] == target:
                return i
        return -1
    def binarySearch(self,arr, target, low, high):
        if low <= high:
            mid = (low + high) // 2
            if arr[mid] == target:
                return mid
            elif arr[mid] < target:
                return binarySearch(arr, target, mid + 1, high)
            else:
                return binarySearch(arr, target, low, mid - 1)
        else:
            return -1
    def bubbleSortSub(self,n, currentPass, arr):
        for i in range(0,n-1-currentPass):
            if arr[i] > arr[i + 1]:
                arr[i], arr[i + 1] = arr[i + 1], arr[i]
                swapped = True
        return
    def sortBubble(self,arr):
        n = len(arr)
        max = n-1
        with tqdm(range(len(arr) - 1, 0, -1), desc="Bubble Sorting", colour="RED",leave=True, ncols=100) as pbar:
            currentPass = 0
            while currentPass < max:# in range(len(arr) - 1, 0, -1):
                swapped = False
                bubbleSortSub(n, currentPass, arr)
                currentPass += 1
                pbar.update(1)
                if not swapped:
                    remUpdates = max - pbar.n # pbar.n is current position
                    if remUpdates > 0: # Only update if there's progress left
                        pbar.update(remUpdates)
                    break
        return arr
    def sortInsert(self,arr):
        n = len(arr)
        if n <= 1:
            return
        for i in tqdm(range(1, n), desc="Insert Sorting", colour="GREEN",leave=True, ncols=100):
            key = arr[i]
            j = i-1
            while j >= 0 and key < arr[j]:
                arr[j+1] = arr[j]
                j -= 1
            arr[j+1] = key
        return arr
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
class MenuBreak(Exception): #Inheritance of the exception class. Making a custom class to raise user raised errors.
    def __init__(self, code, message="Menu Break"):
        self.code = code
        self.message = message
        super().__init__(self.message)
    def __str__(self):
        return self.code
class DataBase(DataObject):
    def __init__(self, city:str="Währing, Wien, Austria", name:str=None, dataBrought:bool=True):
        super().__init__(dataBrought=dataBrought, city=city, name=name)
        self.restaurants = []
        self.cuisines = set()
        self.chains = set()
        with open('./catagories.json',"r") as file:
            catagories = json.loads(file.read())
        records = self.dataPull.to_dict('records')
        for row in tqdm(records,desc="Adding Entities"):
            #tqdm(,total=self.dataPull.__len__(),desc="Adding Entity")
            data = {}
            for newCol, mappedCols in catagories.items():
                dict_ = {}
                for item in mappedCols:
                    if row.get(item) != None and pd.notna(row.get(item)) and row.get(item) != "":
                        dict_[item] = row[item]
                if dict_ != {}:
                    data[newCol] = dict_

            cuisine = getSecond(data,"menuCuisneAttr","cuisine")
            if cuisine != None:
                if ";" in cuisine:
                    cuisine = cuisine.split(";")
                elif "," in cuisine:
                    cuisine = cuisine.split(",")
                for i in cuisine:
                    self.cuisines.add(i)

            if getSecond(data,'operatorAttr','brand') == None:
                self.chains.add(getSecond(data,'operatorAttr','brand'))
                self.restaurants.append(Chain(data))
            else:
                self.restaurants.append(Restaurant(data))
        self.distanceSorted = False
        self.addrSet = False
        self.custSearch = False
        self.cuisines = list(self.cuisines)
        self.cuisines.sort()
        self.defualtSort = ['1']
        self.defualtSearch = ['1']
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
        if False == self.distanceSorted:
            print("Getting Distances...")
            for i in tqdm(self.restaurants, desc="Getting Distances"):
                i.distanceFromCrow(self.addressCoords)
                i.queryScore = 0
                # try :
                #     if i.distanceFrom is None:
                #         i.distanceFromCrow(self.addressCoords)
                #     else:
                #         i.distanceFromCrow(self.addressCoords)
                # except:
                #     i.distanceFromCrow(self.addressCoords)
            print("Sorting...")
            self.restaurants.sort(key=lambda x: x.distanceFrom)
            self.distanceSorted = True
        elif self.custSearch == True:
            self.restaurants.sort(key=lambda x: x.distanceFrom)
            self.distanceSorted = True
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
                if self.custSearch == True:
                    table.field_names = ["#","id","Name", "Amenity","Cuisine", "Location", "Distance", "Search Score"]
                    for r in self.restaurants[:n]:
                        queryScore = getattr(r, "queryScore", None)
                        if r.distanceFrom < 1:
                            distance = str(int(round(r.distanceFrom,3)*1000)) +" m"
                        else:
                            distance = str(round(r.distanceFrom,2)) + " km"
                        menuC = getattr(r,'menuCuisineAttr',{})
                        cuisine = getattr(menuC,'cuisine',None)
                        table.add_row([count, r.id, r.name, r.amenity, cuisine, r.location, distance, f"{queryScore} points" if queryScore is not None else ""])
                        #print(f"{count}: - {i}")
                        count+=1
                else:
                    table.field_names = ["#","id","Name", "Amenity","Cuisine", "Location", "Distance"]
                    for r in self.restaurants[:n]:
                        queryScore = getattr(r, "queryScore", None)
                        if r.distanceFrom < 1:
                            distance = str(int(round(r.distanceFrom,3)*1000)) +" m"
                        else:
                            distance = str(round(r.distanceFrom,2)) + " km"
                        menuC = getattr(r,'menuCuisineAttr',{})
                        cuisine = menuC.get('cuisine')
                        table.add_row([count, r.id, r.name, r.amenity, cuisine, r.location, distance])
                        #print(f"{count}: - {i}")
                        count+=1
                print(table)
                print("===================")
                choice = getInput("Press 'q' to quit or 'm' to return to the menu\nEnter the number of the restaurant you want to see: ")
                choice = int(choice)
                match choice:
                    case choice if choice < 0 or choice > len(self.restaurants):
                        print(f"Choice '{choice}' is out of range of list, please try again.")
                    case choice if type(choice) != int:
                        print(f"Choice '{choice}' is not an integer, please try again.")
                    case _:
                        value = self.restaurants[choice-1].selector()
            except MenuBreak as e:
                raise MenuBreak(e.args)
            except Exception as e:
                print(f"Invalid. Error: '{e}'.")
                SubProcess = False
                continue
            except:
                print("Invalid input, please enter a number.")
                SubProcess = False
                continue
        return self.restaurants[choice-1]         
    def checkUserAddr(self):
        if self.addrSet == False:
            _ = False
            while _ == False:
                self.inpUsrAddress = getInput("Enter your address: ")
                _ = self.usrGetCoords(self.inpUsrAddress)
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
                print(f"Address '{self.inpUsrAddress}' was normalized to '{str(self.usrAddress['addr:street']+" "+self.usrAddress['addr:housenumber']+", "+self.usrAddress['addr:postcode']+" "+self.usrAddress['addr:city'])}' at '{self.addressCoords}'")
            except:
                raise SystemError(response.status_code)
            self.addrSet = True
            self.distanceSorted = False
            #self.distanceSorted = False
        if self.distanceSorted == False:
            self.getClosestList()
    def breakInput(self, inpt):
        if inpt == "q":
            return True
        else:
            return False      
    
    def searchOptionsM(self) -> str:
        print('1. Set Default Search Algorithm\n2. Set Defualt Sort Algorithm. \n3. Test Search Algorithm speed')
        inpt2 = getInput("Select an option: ")
        match inpt2:
            case inpt2 if inpt2 == '1':
                print('1. Binary Search\n2. Linear Search')
                inpt3 = getInput("Select any combination of options (i.e. 1,3,4 or 413)")
                if "," in inpt3:
                    inpt3 = inpt3.split(',')
                else:
                    inpt3 = list(inpt3)
                inpt3.sort()
                self.defualtSearch = inpt3
            case inpt2 if inpt2 == '2':
                print('1. Bubble Sort\n2. Insert Sort')
                inpt3 = getInput("Select any combination of options (i.e. 1,3,4 or 413)")
                if "," in inpt3:
                    inpt3 = inpt3.split(',')
                else:
                    inpt3 = list(inpt3)
                inpt3.sort()
                self.defualtSort = inpt3
            case inpt2 if inpt2 == '3':
                return '2'

        return
    def run(self):
        print("Welcome to the Restaurant Finder!\n(At any point press 'q' to quit or 'm' to return to the menu.)")
        b = False
        while b == False:
            try:
                choice = self.display_menu()
                if choice == '1':
                    self.checkUserAddr()
                    Search = SearchQuery()
                    if Search.menu() == False:
                        raise MenuBreak("m")
                    # print("Searching...")
                    for i in self.restaurants:
                        i.queryScore = Search.evaluateQuery(i)
                    # print("Sorting...")
                    ## RestaurantsCopy = self.restaurants.copy()
                    ## RestaurantsCopy = [x for x in RestaurantsCopy if x.queryScore >= 2]
                    # self.restaurants.sort(key=lambda x: int(x.queryScore), reverse=True)
                    self.custSearch = True
                    print(Search)
                    resp = self.restrauntListPresenter()
                elif choice == '2':
                    self.checkUserAddr()                     
                    self.restrauntListPresenter()
                elif choice == "3":
                    for i in self.cuisines:
                        print(i)
                elif choice == '4':
                    self.addrSet = False
                    self.distanceSorted = False
                    self.checkUserAddr()
                elif choice == '5':
                    self.searchOptionsM()
                elif choice == '6':
                    raise MenuBreak("q")
                elif choice == 'debug':
                    inp = None
                    while inp != "quit":
                        inp = getInput("Code: ")
                        print(eval(inp,globals(),locals()))
                else:
                    print("Invalid Input. Try agian or press 'q' to quit.")
            except MenuBreak as e:
                if e.code == "q":
                    b = True
                elif e.code == "m":
                    continue
            except Exception as e:
                print(f"Something went wrong. Error: {e}") 
    def display_menu(self):
        print("\nMENU:")
        print("1. Search Restaurants")
        print("2. Show closest restaurants")
        print("3. Show all Cuisines")
        print("4. Set User Location")
        print("5. Search Options")
        print("6. Exit")
        return getInput("Enter choice: ")
if __name__ == "__main__":
    # do = DataObject(dataBrought=True, city="Wien, Austria", name="../Vienna OSM expanded data/Wien_Restaurants-Expanded")
    # do.dataPull.head()
    # try:
    dp = DataBase(dataBrought=True, city="Wien, Austria", name="./Wien_Restaurants-Combined")
    dp.run()
    # except Exception as e:
        
    #     # print(e.with_traceback())
    #     q = True
    #     e
    #     print(e)
    #     print(e.args)
    #     while q == True:
    #         inp = input(":")
    #         if inp == "q":
    #             q = False
    #         print(eval(inp,globals(),locals()))

        
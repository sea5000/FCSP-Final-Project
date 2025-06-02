from abc import ABC, abstractmethod
import osmnx as ox
import pandas as pd
from tqdm import tqdm
from shapely.geometry import Point
import datetime as dt
import re
from geopy.distance import geodesic
from pyproj import CRS, Transformer
import requests
import json
import time
from prettytable import PrettyTable
import csv
import math

weekdayMap = {
    r'\b(Mon|Montag|Mo)\b': 'Mo',
    r'\b(Tue|Tues|Dienstag|Di)\b': 'Tu',
    r'\b(Wed|Mittwoch|Mi)\b': 'We',
    r'\b(Thu|Thur|Donnerstag|Do)\b': 'Th',
    r'\b(Fri|Freitag|Fr)\b': 'Fr',
    r'\b(Sat|Samstag|Sa)\b': 'Sa',
    r'\b(Sun|Sonntag|So)\b': 'Su',
}
customBarFormatMS = (
    '{l_bar}{bar}| {n_fmt}/{total_fmt} '
    '[{elapsed_s:.3f}s<{remaining_s:.3f}s, '  # Formats to 3 decimal places (milliseconds)
    '{rate_fmt}]'
)
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
def getInput(prompt:str, dataType) ->str:
    while True:
        try:
            inp = input(prompt).strip()
            if inp.lower() == "q":
                raise MenuBreak("q")
            elif inp.lower() == "m":
                raise MenuBreak("m")
            if dataType == bool:
                if inp.lower() in ['yes', 'y']:
                    return True
                elif inp.lower() in ['no', 'n']:
                    return False
                elif inp == '':
                    return None # Represents 'any'
                else:
                    raise ValueError("Please enter 'yes', 'no', or leave blank.")
            elif inp == '' and dataType is not str: # Allow empty for non-string optional inputs
                 return None
            return dataType(inp) if inp else None
        except MenuBreak as e:
            raise MenuBreak(e.code)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
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
def printLogo():
    print("""================================================================

██████╗   █████╗ ████████╗ █████╗ ██████╗ ██╗███╗   ██╗███████╗
██╔══██╗ ██╔══██╗╚══██╔══╝██╔══██╗██╔══██╗██║████╗  ██║██╔════╝
██║  ██║ ███████║   ██║   ███████║██║  ██║██║██╔██╗ ██║█████╗
██║  ██║ ██╔══██║   ██║   ██╔══██║██║  ██║██║██║╚██╗██║██╔══╝
██████╔╝ ██║  ██║   ██║   ██║  ██║██████╔╝██║██║ ╚████║███████╗
╚═════╝  ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚═╝╚═╝  ╚═══╝╚══════╝

================================================================""")
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
        
        restaurants = ox.features_from_place(self.city, tags)            
       
        restaurants['id'] = [i[1] for i in restaurants.index]#Sets the ID for the restraunt form the index to the id column
        restaurants["lat"] = restaurants['geometry'].apply(lambda x: re.search(r'(\d+[.]{1}\d+[ ]\d+[.]{1}\d+)', str(x)).group(0).split(" ")[1]) # Grabs the lat coord from the geometry field.
        restaurants["long"] = restaurants['geometry'].apply(lambda x: re.search(r'(\d+[.]{1}\d+[ ]\d+[.]{1}\d+)', str(x)).group(0).split(" ")[0]) # Grabs the long coord from the geometry field.
        restaurants = restaurants.drop(columns=['geometry']) # Removes teh now redundant geometry field.
        if populateAddress: # If this is true (default it is) this will populate addressess based of the lat and long. Although there is good data in OSM, I opted for losing some accuracy in the address and having a complete address dataset.
            start_time = time.time()
            working = restaurants.to_dict("records")
            for index, row in tqdm(enumerate(working),total=len(working),colour="#328ba8",desc="Normalizing Addresses",bar_format=customBarFormatMS,leave=True, ncols=100):
                lat = row['lat']
                long = row['long']
                url = f"https://data.wien.gv.at/daten/OGDAddressService.svc/ReverseGeocode?location={row['long']},{row['lat']}&crs=WGS84"
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
        return f"{self.street} {self.house}, {self.district}"

class OpenHours:
    def __init__(self, hours:str|None):
        if hours == None:
            self.hours = None
        else:
            hours = re.sub(r'(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})', r'\1-\2', hours)
            self.hours = ParseHours(hours)
    def __str__(self):
        return str(self.hours)
    def is_open(self, checkDatetime=None):
        if not self.schedule:
            return None # Represents "Data not available"

        if checkDatetime is None:
            checkDatetime = dt.datetime.now()

        dayAbbr = checkDatetime.strftime("%a")[:2] # Mo, Tu, We...
        currentTime = checkDatetime.time()

        if dayAbbr not in self.schedule:
            return False # Closed if day not in schedule

        daySchedule = self.schedule[dayAbbr]
        if not daySchedule or "OFF" in daySchedule:
            return False

        for timeRangeStr in daySchedule:
            try:
                startStr, end_str = timeRangeStr.split('-')
                startTime = dt.datetime.strptime(startStr, "%H:%M").time()
                
                # Handle 24:00 as end of day
                if end_str == "24:00":
                    end_time = dt.time(23, 59, 59)
                else:
                    end_time = dt.datetime.strptime(end_str, "%H:%M").time()

                if startTime <= end_time: # Normal same-day range
                    if startTime <= currentTime <= end_time:
                        return True
                else: # Overnight range (e.g., 22:00-02:00)
                    if currentTime >= startTime or currentTime <= end_time:
                        return True
            except ValueError:
                continue # Skip malformed time range
        return False
    def __getitem__(self, key):
        return self.hours.get(key) if self.hours else None
    def isCurrentlyOpen(self):
        now = dt.datetime.now()
        currentDay = now.strftime("%a")  # e.g. "Mon"
        currentTime = now.time()  # datetime.time object directly
        currentMonth = now.strftime("%b")  # e.g. "Apr"
        if self.hours is None:
            return None
        if len(self.hours) > 8:
            if currentMonth not in self.hours:
                # print(f"{currentMonth} not in self.hours: {self.hours.keys()}")
                return False
            hourInfo = self.hours[currentMonth]
            if hourInfo == {} or hourInfo.get(currentDay) == None:
                return False
            hours = hourInfo[currentDay]
        else:
            if currentDay not in self.hours:
                return False
            hours = self.hours[currentDay]
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
class Place(ABC):
    def __init__(self, identity, name, location_obj, hours_obj, cuisine_list=None, outdoor_seating=None):
        self.identity = identity
        self.name = name
        self.location = location_obj
        self.hours = hours_obj
        self.cuisine = cuisine_list if cuisine_list else []
        self.outdoor_seating = outdoor_seating # True, False, or None
        self.distanceFromUser = None
    @abstractmethod
    def getSearchAttr(self):
        ...
    @abstractmethod
    def isCurrentlyOpen(self):
        ...
    def getDisplayAttributes(self):
        open_status = self.hours.isCurrentlyOpen()
        if open_status is None:
            open_display = "Hours N/A"
        elif open_status:
            open_display = "Open Now"
        else:
            open_display = "Closed Now"
            

        if self.distanceFromUser is not None:
            if self.distanceFromUser < 1:
                distance = f"{round(self.distanceFromUser*1000)} m"
            else:
                distance = f"{self.distanceFromUser:.2f} km"
        else:
            distance = "N/A"

        details = [
            self.identity,
            self.name,
            ", ".join(self.cuisine) if self.cuisine else "N/A",
            distance,
            str(self.location),
            open_display,
            self.amenity
        ]
        return details
    def distanceFromCrow(self, userPoint: tuple):
        if self.location.lat is not None and self.location.long is not None:
            try:
                restaurant_point = (float(self.location.lat), float(self.location.long))
                self.distanceFromUser = geodesic(userPoint, restaurant_point).km
            except (ValueError, TypeError):
                self.distanceFromUser = None
        else:
            self.distanceFromUser = None
        return self.distanceFromUser
    def __lt__(self, other): # For sorting
        if self.distanceFromUser is None and other.distanceFromUser is None:
            return self.name < other.name
        if self.distanceFromUser is None:
            return False # None is considered greater
        if other.distanceFromUser is None:
            return True # other.None is greater
        
        # Primary sort by distance, secondary by name
        if self.distanceFromUser != other.distanceFromUser:
            return self.distanceFromUser < other.distanceFromUser
        return self.name.lower() < other.name.lower()
    def __le__(self,other):
        if self.distanceFromUser is None and other.distanceFromUser is None:
            return self.name < other.name
        if self.distanceFromUser is None:
            return False # None is considered greater
        if other.distanceFromUser is None:
            return True # other.None is greater
        
        # Primary sort by distance, secondary by name
        if self.distanceFromUser != other.distanceFromUser:
            return self.distanceFromUser <= other.distanceFromUser
        return self.name.lower() < other.name.lower()
class Restaurant(Place):
    def __init__(self, identity, name, location_obj, hours_obj, cuisine_list, amenity, outdoor_seating=None, phone=None, website=None, wheelchair=None):
        super().__init__(identity, name, location_obj, hours_obj, cuisine_list, outdoor_seating)
        self.amenity = amenity # E.g. restaurant, cafe, bar
        self.phone = phone
        self.website = website
        self.wheelchairAccessible = wheelchair # True, False, or None
    def __str__(self):
        queryScore = getattr(self, "queryScore", None)
        if self.distanceFrom < 1:
            distance = str(int(round(self.distanceFrom,3)*1000)) +" m"
        else:
            distance = str(round(self.distanceFrom,2)) + " km"
        return f"{self.identity} - {self.name} ({', '.join(self.cuisine)}) - {self.location} - {distance}" + (f" - {self.queryScore} points" if queryScore is not None else "")
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
    def getSearchAttr(self):
        if self.outdoor_seating is not None:
            if self.outdoor_seating != "no":
                attrOutdoorSeating = True
            else:
                attrOutdoorSeating = False
        else:
            attrOutdoorSeating = None
        if self.wheelchairAccessible is not None:
            if self.wheelchairAccessible != "no" and self.wheelchairAccessible is not None:
                        attrWheelchairAccessible = True
            else:
                attrWheelchairAccessible = False
        else:
            attrWheelchairAccessible = None
        return {
                "name": self.name.lower() if self.name else None,
                "cuisine": [c.lower() for c in self.cuisine],
                "outdoor_seating": attrOutdoorSeating,
                "is_open": self.hours.isCurrentlyOpen(),
                "district": self.location.district if self.location.district else None,
                "wheelchairAssc": attrWheelchairAccessible
            }
    
    # def distanceFromCrow(self, userPoint):
        try:
            resPoint = Point(float(self.location.lat), float(self.location.long))
            self.distanceFrom = geodesic((userPoint[0], userPoint[1]), (resPoint.y, resPoint.x)).kilometers
        except:
            print(self.name,self.location['lat'],self.location['long'])
        return self.distanceFrom
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
    #['restaurant', 'pub', 'cafe', 'fast_food', 'bar', 'food_court', 'biergarten', 'ice_cream']
class Chain(Place):
    def __init__(self, identity, name, location_obj, hours_obj, cuisine_list, amenity, outdoor_seating=None, phone=None, website=None, wheelchair=None,chain=None):
        super().__init__(identity, name, location_obj, hours_obj, cuisine_list, outdoor_seating)
        self.amenity = amenity # E.g. restaurant, cafe, bar
        self.phone = phone
        self.chain = chain
        self.website = website
        self.wheelchairAccessible = wheelchair # True, False, or None
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
    def getDisplayAttributes(self):
        # Polymorphic override: Add chain information
        base_details = super().getDisplayAttributes()
        base_details[1] = f"{self.name} ({self.chain} Chain)" # Modify name
        return base_details
    def getSearchAttr(self):
        if self.outdoor_seating is not None:
            if self.outdoor_seating != "no":
                attrOutdoorSeating = True
            else:
                attrOutdoorSeating = False
        else:
            attrOutdoorSeating = None
        if self.wheelchairAccessible is not None:
            if self.wheelchairAccessible != "no" and self.wheelchairAccessible is not None:
                        attrWheelchairAccessible = True
            else:
                attrWheelchairAccessible = False
        else:
            attrWheelchairAccessible = None
        return {
                "name": self.name.lower() if self.name else None,
                "cuisine": [c.lower() for c in self.cuisine],
                "outdoor_seating": attrOutdoorSeating,
                "is_open": self.hours.isCurrentlyOpen(),
                "district": self.location.district if self.location.district else None,
                "wheelchairAssc": attrWheelchairAccessible
            }
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
    def __str__(self):
        queryScore = getattr(self, "queryScore", None)
        if self.distanceFrom < 1:
            distance = str(int(round(self.distanceFrom,3)*1000)) +" m"
        else:
            distance = str(round(self.distanceFrom,2)) + " km"
        return f"{self.identity} - {self.name} ({', '.join(self.cuisine)}) - {self.location} - {distance}" + (f" - {self.queryScore} points" if queryScore is not None else "")
    def __repr__(self):
        return f"{self.name} - {type(self)} - {self.location}"
    # def distanceFromCrow(self, userPoint):
        try:
            resPoint = Point(float(self.location.lat), float(self.location.long))
            self.distanceFrom = geodesic((userPoint[0], userPoint[1]), (resPoint.y, resPoint.x)).kilometers
        except:
            print(self.name,self.location.lat,self.location.long)
        return self.distanceFrom

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
        
        self.distanceSorted = False
        self.addrSet = False
        self.custSearch = False
        self.defaultSort = ['2']
        #self.defaultSearch = ['1']
        self.loadFromDO()
        self.cuisines = self._extractUniqueCuisines()

    def __getitem__(self, key):
        if hasattr(self, key):
            return getattr(self, key)
    def _extractUniqueCuisines(self):
        allCuisines = set()
        for r in self.restaurants:
            if r.cuisine:
                for c in r.cuisine:
                    #print(c if c.location = 'Pizza')
                    allCuisines.add(c.strip().lower())
        return sorted(list(allCuisines))
    def loadFromDO(self):
        records = self.dataPull.to_dict('records')
        for row in tqdm(records,desc="Adding Entities", bar_format=customBarFormatMS, colour="RED",leave=True, ncols=100):
            cuisine = row['cuisine']
            if pd.notna(cuisine):# and cuisine != None:
                if ";" in cuisine:
                    cuisine = [str(x).strip().lower() for x in cuisine.split(";")]
                elif "," in cuisine:
                    cuisine = [str(x).strip().lower() for x in cuisine.split(",")]
                else:
                    cuisine = [str(cuisine)]
            else:
                cuisine = None
            lat = float(row['lat'])
            identity = int(row['id'])
            long = float(row['long'])
            city = str(row['addr:city'] if pd.notna(row['addr:city']) else "")
            street = str(row['addr:street'] if pd.notna(row['addr:street']) else "")
            house = str(row['addr:housenumber'] if pd.notna(row['addr:housenumber']) else "")
            district = int(row['addr:postcode']) if pd.notna(row['addr:postcode']) else None
            location_obj = Location(lat, long, district, street, house)
            hours = str(row['opening_hours'])
            hours_obj = OpenHours(hours)
            name = str(row['name'])
            amenity = str(row['amenity'])
            outdoor_seating = str(row['outdoor_seating'] if pd.notna(row['outdoor_seating']) else "")
            phone = str(row['phone'] if pd.notna(row['phone']) else "")
            website = str(row['website'] if pd.notna(row['website']) else "")
            wheelchair = str(row['wheelchair'] if pd.notna(row['wheelchair']) else "")
            chain = row['brand']
            #id, name, location_obj, hours_obj, cuisine_list, amenity, outdoor_seating=None, phone=None, website=None, wheelchair=None,chain=None)
            if pd.notna(chain) == True:
                self.restaurants.append(Chain(identity, name, location_obj, hours_obj, cuisine, amenity, outdoor_seating, phone, website, wheelchair, str(chain)))
            else:
                self.restaurants.append(Restaurant(identity, name, location_obj, hours_obj, cuisine, amenity, outdoor_seating, phone, website, wheelchair))
    def getFilteredRestaurants(self, criteria):
        """
        Filters restaurants based on complex criteria.
        criteria: dict like {'cuisine': ['italian', 'pizza'], 'open_now': True, 'outdoor': True, 'district': '1010', 'logic': 'AND'}
        """
        if not self.restaurants:
            return []

        filteredList = []
        logicOperator = criteria.get('logic', 'AND').upper() # Defaults to AND if logic dict entry is None or doesn't exist.

        #Linear Search Algorithm
        for restaurant in tqdm(self.restaurants,bar_format=customBarFormatMS,desc="Linear Searching", colour="#6232a8",leave=True, ncols=100):
            if self.evalRes(restaurant, criteria, logicOperator):
                filteredList.append(restaurant)

        return filteredList
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
            #print("Getting Distances...")
            for i in tqdm(self.restaurants,bar_format=customBarFormatMS, desc="Getting Distances", colour="CYAN",leave=True, ncols=100):
                i.distanceFromCrow(self.addressCoords)
                i.queryScore = 0
                # try :
                #     if i.distanceFrom is None:
                #         i.distanceFromCrow(self.addressCoords)
                #     else:
                #         i.distanceFromCrow(self.addressCoords)
                # except:
                #     i.distanceFromCrow(self.addressCoords)
            #print("Sorting...")
            for i in self.defaultSort: 
                copy = self.restaurants.copy()


            #self.restaurants.sort(key=lambda x: x.distanceFrom)
            self.distanceSorted = True
        elif self.custSearch == True:
            self.restaurants.sort(key=lambda x: x.distanceFrom)
            self.distanceSorted = True
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
    def displayRestaurants(self, sortedList, maxDisplay:int=10):
        if not sortedList:
            print("No restaurants to display.")
            return

        table = PrettyTable()
        
        table.field_names = ["#", "Name", "Cuisine(s)","Distance", "Location - Open Status"]
        
        for i, restaurant in enumerate(sortedList,start=1):
            if i > maxDisplay:
                print(f"... and {len(sortedList) - maxDisplay} more. Refine your search or see all.")
                break
            try:
                details = restaurant.getDisplayAttributes()
                # Ensure the number of details matches the number of field names
                table.add_row([i, details[1], details[2], details[3],", ".join(map(str,details[4:6])) if len(details) > 2 else "N/A"])
                """if len(details) == len(table.field_names):
                    table.add_row([(j,k) for j,k in details.items()])
                else:
                    # Fallback if detail structure doesn't match
                    table.add_row([i, details[1], details[2],", ".join(map(str,details[3:])) if len(details) > 2 else "N/A"] + [""] * (len(table.field_names) - 3))"""
            except Exception as e:
                print(f"Error displaying restaurant {restaurant.name}: {e}")
                # Add a row with error info if needed
                table.add_row([i,restaurant.name,"Err","Err" if hasattr(restaurant,'name') else 'Error Name', str(e)] + [""] * (len(table.field_names) - 4))
        #table.add_column("#",[i for i in range(1,len(maxDisplay)),])
        print(table)
    def showCuisines(self):
        print("\n--- Available Cuisines ---")
        if self.cuisines:
            for i, cuisine in enumerate(self.cuisines):
                print(f"{i+1}. {cuisine.capitalize()}")
        else:
            print("No cuisine data available.")    
    def checkUserAddr(self):
        if self.addrSet == False:
            _ = False
            while _ == False:
                self.inpUsrAddress = getInput("Enter your address: ",str)
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
    def evalRes(self,restaurant:Place, criteria:dict, logicOperator:str) -> bool:
        #Takes restaurant and the criteria and returns bool if the restaurant meets that criteria
        attrs = restaurant.getSearchAttr()
        matchConditions = []

        # Cuisine check (OR logic within cuisines)
        if criteria.get('cuisine'):
            desiredCuisines = set([c.lower().strip() for c in criteria['cuisine']])
            attrCuisineSet = set(attrs['cuisine'])
            matchedCuisines = attrCuisineSet & desiredCuisines #Intersection of set
            if matchedCuisines:
                matchConditions.append(True)
            else:
                matchConditions.append(False)
        else:
            matchConditions.append(True) # No cuisine specified, so it's a match for this part

        # Outdoor seating
        if criteria.get('outdoor_seating') is not None:
            if attrs['outdoor_seating'] == criteria['outdoor_seating']:
                matchConditions.append(True)
            else:
                matchConditions.append(False)
        else:
            matchConditions.append(True)

        # Open now
        if criteria.get('open_now') is not None:
            # is_open() can return None if data is unavailable. Treat None as not matching a specific True/False request.
            if attrs['is_open'] is None and criteria['open_now'] is not None: # User wants specific open/closed, but data is N/A
                matchConditions.append(False)
            elif attrs['is_open'] == criteria['open_now']:
                matchConditions.append(True)
            else:
                matchConditions.append(False)
        else:
            matchConditions.append(True)
        
        # District
        if criteria.get('district'):
            if attrs['district'] and criteria['district'] == attrs['district']:
                matchConditions.append(True)
            else:
                matchConditions.append(False)
        else:
            matchConditions.append(True)

        if criteria.get('wheelchairAccessible') is not None:
            # is_open() can return None if data is unavailable. Treat None as not matching a specific True/False request.
            if attrs['is_open'] is None and criteria['open_now'] is not None: # User wants specific open/closed, but data is N/A
                matchConditions.append(False)
            elif attrs['is_open'] == criteria['open_now']:
                matchConditions.append(True)
            else:
                matchConditions.append(False)
        else:
            matchConditions.append(True)


        # Combine conditions
        if logicOperator == 'AND':
            if all(matchConditions):
                return True
        elif logicOperator == 'OR':
            # For OR, we need to be careful. If no criteria are set, it's a match.
            # If criteria ARE set, then at least one specific criterion must match.
            # This current structure of match_conditions[] appending True for non-specified
            # criteria doesn't work well for OR. Let's adjust for OR.

            # Re-evaluate for OR:
            # A restaurant matches if ANY of the *specified* criteria are met.
            # If a criterion is NOT specified by the user, it doesn't contribute to an OR match.
            
            if not any(k in criteria for k in ['cuisine', 'wheelchairAccessible', 'outdoor_seating', 'open_now', 'district']):
                # No criteria actually specified for the OR search, means match all (or none, depending on interpretation)
                # Let's say it matches all if no specific OR conditions given.
                return True
                #continue

            or_match = False
            if criteria.get('cuisine'):
                desiredCuisines = [c.lower().strip() for c in criteria['cuisine']]
                if any(c in attrs['cuisine'] for c in desiredCuisines):
                    or_match = True
            
            if not or_match and criteria.get('outdoor_seating') is not None:
                if attrs['outdoor_seating'] == criteria['outdoor_seating']:
                    or_match = True
            
            if not or_match and criteria.get('open_now') is not None:
                if attrs['is_open'] is not None and attrs['is_open'] == criteria['open_now']:
                    or_match = True
            
            if not or_match and criteria.get('district'):
                if attrs['district'] and criteria['district'] == attrs['district']:
                    or_match = True

            if not or_match and criteria.get('wheelchairAccessible'):
                if attrs['wheelchairAccessible'] and criteria['wheelchairAccessible'].lower() == attrs['wheelchairAccessible']:
                    or_match = True
            
            if or_match:
                    return True
    def advanced_search_ui(self):
        print("\n--- Advanced Restaurant Search ---")
        print("Leave blank for any option.")
        cuisines_input = getInput("Enter desired cuisine(s) (comma-separated, multiples will be or searched): ", str)
        desired_cuisines = [c.strip() for c in cuisines_input.split(',')] if cuisines_input else None

        outdoor_seating_input = getInput("Needs outdoor seating? (yes/no): ", bool)
        open_now_input = getInput("Needs to be open now? (yes/no): ", bool)
        
        district_input_str = getInput("Enter district (e.g., 1010 or 1 (for 1st)): ", str)
        district_input = None
        if district_input_str:
            if district_input_str.isdigit() and int(district_input_str) <= 23 and int(district_input_str) >= 0:
                if len(district_input_str) <= 2: # e.g. 1, 7, 10, 23
                    district_input = int("1"+district_input_str.zfill(2)+"0")# "1" + district_input_str.zfill(1) if len(district_input_str) < 3 else district_input_str
                elif len(district_input_str) == 4 and district_input_str.startswith("1"): # e.g. 1010, 1230
                     district_input = int(district_input_str)
                else:
                    print("Invalid district format. Searching all districts.")
            else:
                print("Invalid district format. Searching all districts.")


        logic_choice = getInput("Combine criteria with AND or OR? (and/or): ", str)
        logic = 'AND'
        if logic_choice and logic_choice.upper() == 'OR':
            logic = 'OR'
        
        search_criteria = {
            'cuisine': desired_cuisines,
            'outdoor_seating': outdoor_seating_input,
            'open_now': open_now_input,
            'district': district_input,
            'logic': logic
        }
        
        print(f"\nSearching with criteria: {search_criteria}")
        results = self.getFilteredRestaurants(search_criteria)
        
        results = self.sortAlg(results)
        # if self.addressCoords:
        #     for r in results:
        #         r.calculate_distance(self.addressCoords[0], self.addressCoords[1])
        #     # Default sort by distance if location is known
        #     results = self.sortAlg(results)
        # else:
        #     # Default sort by name if no location
             


        self.displayRestaurants(results)
        if results:
            if getInput("Save these results to CSV? (yes/no): ", bool):
                filename = getInput("Enter filename (e.g., search_results.csv): ", str)
                if filename:
                    self.saveRToCSV(results, filename)
    def sortInsert(self,arr):
        n = len(arr)
        if n <= 1:
            return
        for i in tqdm(range(1, n), desc="Insert Sorting",bar_format=customBarFormatMS, colour="GREEN",leave=True, ncols=100):
            key = arr[i]
            j = i-1
            while j >= 0 and key < arr[j]:
                arr[j+1] = arr[j]
                j -= 1
            arr[j+1] = key
        return arr
    
    def sortMerge(self, arr):
        n = len(arr)
        if n <= 1:
            return arr
        
        # Initialize tqdm bar for the entire sorting process
        # The total is 'n' because each element eventually passes through a merge.
        # tqdm's default bar format will be used.
        totalOps = int(n * math.ceil(math.log2(n))) 
        with tqdm(total=totalOps, desc="Merge Sorting",bar_format=customBarFormatMS, colour="BLUE",leave=True, ncols=100) as pbar:
            self._mergeSortRecursiveHelper(arr, 0, n - 1, pbar)
        
        return arr 

    def _mergeSortRecursiveHelper(self, arr, left_idx, right_idx, pbar: tqdm):
        if left_idx < right_idx:
            mid_idx = (left_idx + right_idx) // 2
            self._mergeSortRecursiveHelper(arr, left_idx, mid_idx, pbar)
            self._mergeSortRecursiveHelper(arr, mid_idx + 1, right_idx, pbar)
            
            # Merge operation is where elements are actually processed and moved.
            # We pass the pbar to update it.
            self._mergeHalves(arr, left_idx, mid_idx, right_idx, pbar)

    def _mergeHalves(self, arr, left_start_idx, mid_idx, right_end_idx, pbar: tqdm):
        left_half_copy = arr[left_start_idx : mid_idx + 1]
        right_half_copy = arr[mid_idx + 1 : right_end_idx + 1]

        i = 0
        j = 0
        k = left_start_idx

        while i < len(left_half_copy) and j < len(right_half_copy):
            if left_half_copy[i] <= right_half_copy[j]:
                arr[k] = left_half_copy[i]
                i += 1
            else:
                arr[k] = right_half_copy[j]
                j += 1
            k += 1
            pbar.update(1) # Update progress for each element placed back into arr

        while i < len(left_half_copy):
            arr[k] = left_half_copy[i]
            i += 1
            k += 1
            pbar.update(1) # Update progress for each element placed back into arr

        while j < len(right_half_copy):
            arr[k] = right_half_copy[j]
            j += 1
            k += 1
            pbar.update(1) # Update progress for each element placed back into arr


    def _sortBubbleSub(self, n, currentPass, arr):
        # Initialize swapped for the current pass
        swapped = False
        for i in range(0, n - 1 - currentPass):
            if arr[i] > arr[i + 1]:
                arr[i], arr[i + 1] = arr[i + 1], arr[i]
                swapped = True # Mark that a swap occurred
        return swapped # Return whether a swap happened in this pass

    def sortBubble(self, arr):
        n = len(arr)
        # The loop for bubble sort goes from n-1 down to 1 (or 0 passes for the last element)
        # The number of passes is n-1.
        # So the total for tqdm should be n-1.
        with tqdm(total=n - 1, desc="Bubble Sorting",bar_format=customBarFormatMS, colour="RED", leave=True, ncols=100) as pbar:
            for currentPass in range(n - 1): # Iterate through the passes
                # Call the sub-function and get the swapped status
                swapped_in_pass = self._sortBubbleSub(n, currentPass, arr)
                pbar.update(1) # Update the progress bar for each completed pass

                # If no swaps occurred in this pass, the array is sorted.
                # We can break early.
                if not swapped_in_pass:
                    # If we break early, we need to ensure the tqdm bar
                    # reaches its total to show completion.
                    rem_updates = pbar.total - pbar.n
                    if rem_updates > 0:
                        pbar.update(rem_updates)
                    break # Exit the loop as the array is sorted

        return arr
    def searchOptionsM(self) -> str:
        print('1. Set Default Sort Algorithm. \n2. Test Search Algorithm speed')
        inpt2 = getInput("Select an option: ",str)
        match inpt2:
            case inpt2 if inpt2 == '1':
                print('1. Bubble Sort\n2. Insert Sort\n3. Merge Sort')
                inpt3 = getInput("Select any combination of options (i.e. 1,3,4 or 413)",str)
                if "," in inpt3:
                    inpt3 = inpt3.split(',')
                else:
                    inpt3 = list(inpt3)
                inpt3.sort()
                self.defaultSort = inpt3
            case inpt2 if inpt2 == '2':
                self.checkUserAddr()
                self.sortBubble(self.restaurants)
                self.sortInsert(self.restaurants)
                self.sortMerge(self.restaurants)
            case inpt2 if inpt2 == '3':
                return '2'

        return
    def sortAlg(self, arr):
        #Sorts based on the list of sort options.
        sortedOutput = None
        for i in self.defaultSort:
            if i == "1":#1. Bubble Sort\n2. Insert Sort\n3. Merge Sort
                sortedOutput = self.sortBubble(arr)
            if i == "2":
                sortedOutput = self.sortInsert(arr)
            if i == "3":
                sortedOutput = self.sortMerge(arr)
        return sortedOutput
    def showClosestRest(self, top_n=10):
        # This uses the sortAlg method to sort the restaurants, then uses displayRestaurants method to display them.
        # Ensure all restaurants have distance calculated
        for r in self.restaurants:
            r.distanceFromCrow((self.addressCoords[0], self.addressCoords[1]))
        
        # Filter out restaurants with no distance and sort
        valid_distance_restaurants = [r for r in self.restaurants if r.distanceFromUser is not None]
        
        # Use Python's sort with the __lt__ method defined in Place/Restaurant
        # 1. Bubble Sort\n2. Insert Sort\n3. Merge Sort
        sorted_restaurants = self.sortAlg(valid_distance_restaurants)

        print(f"\n--- Top {top_n} Closest Restaurants ---")
        self.displayRestaurants(sorted_restaurants[:top_n])
    def saveRToCSV(self, restaurant_list, filename):
        if not restaurant_list:
            print("No results to save.")
            return
        if not filename.endswith(".csv"):
            filename += ".csv"
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                # Write header based on the display details
                if isinstance(restaurant_list[0], Restaurant):
                    header = ["ID", "Name", "Cuisine(s)", "Distance",  "Location", "Open Status", "Type"]
                else: # Fallback
                    header = ["ID", "Name", "Details"]
                writer.writerow(header)
                
                for restaurant in restaurant_list:
                    details = restaurant.getDisplayAttributes()
                    # Ensure details match header length if using specific headers
                    if len(details) == len(header):
                         writer.writerow(details)
                    else: # Fallback if mismatch
                        writer.writerow([details[0], details[1], ", ".join(map(str,details[2:]))])
            print(f"Results saved to {filename}")
        except IOError:
            print(f"Error: Could not write to file {filename}.")
        except Exception as e:
            print(f"An unexpected error occurred while saving: {e}")
    def run(self):
        printLogo()
        print("Welcome to the DataDine Restaurant Finder!\n(At any point press 'q' to quit or 'm' to return to the menu.)")
        b = False
        while b == False:
            try:
                choice = self.display_menu()
                if choice == '1':
                    self.checkUserAddr()
                    self.advanced_search_ui()
                    #resp = self.displayRestaurants()
                elif choice == '2':
                    self.checkUserAddr()                     
                    self.showClosestRest()
                elif choice == "3":
                    self.showCuisines()
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
                        inp = getInput("Code: ",str)
                        print(eval(inp,globals(),locals()))
                else:
                    print("Invalid Input. Try agian or press 'q' to quit.")
            except MenuBreak as e:
                if e.code == "q":
                    b = False
                elif e.code == "m":
                    continue
            except Exception as e:
                print(f"Something went wrong. Error: {e}")
        print("Goodbye!")
    def display_menu(self):
        print("\nMENU:")
        print("1. Search Restaurants")
        print("2. Show closest restaurants")
        print("3. Show all Cuisines")
        print("4. Set User Location")
        print("5. Search Options")
        print("6. Exit")
        return getInput("Enter choice: ",str)
if __name__ == "__main__":
    dp = DataBase(dataBrought=True, city="Wien, Austria", name="./Wien_Restaurants-Combined")
    dp.run()

        
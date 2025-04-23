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
        # def get_cuisine_or_amenity(row):
        #     if row['amenity'] == 'restaurant' and pd.notna(row['cuisine']):
        #         return row['cuisine']
        #     else:
        #         return row['amenity']
            
        # restaurants['cuisine_or_amenity'] = restaurants.apply(get_cuisine_or_amenity, axis=1)

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
                    
        self.data = restaurants.dropna(subset=['name']) #[['id', 'name', 'lat', 'long', 'addr:street', 'addr:housenumber', 'addr:city', 'addr:postcode', "cuisine_or_amenity","opening_hours"]]
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
        return f"{self.id} - {self.name} ({self.cuisine}) - {self.location} - {self.distanceFrom} km" + (f" - {self.queryScore}" if queryScore is not None else "")

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
                    case choice if choice == "q":
                        return "q"
                    case choice if choice == "":
                        print("No choice made, please try again.")
                    case choice if int(choice) > count:
                        print("Invalid choice, please try again.")
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
        # super().__init__(dataBrought=self.dataBrought, city=self.city, name=name)
        self.city = city
        self.restaurants = []
        self.dataBrought = dataBrought
        self.dataPull = DataObject(dataBrought=self.dataBrought, city=self.city, name=name)
        self.data = self.dataPull.data
        self.cuisines = set()
        for index, row in self.data.iterrows():
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
        ...
        # for i in self.restaurants:
        #     # if i.get("distanceFrom") is None:
        #     #     print("CALCULATING DISTANCE - REMOVE LATER")
        #         i.distanceFromCrow(address)
        self.restaurants.sort(key=lambda x: x.distanceFrom)
        return [str(x) for x in self.restaurants[:n] if x.cuisine == "restaurant"]
    def restrauntListPresenter(self, n:int=10):
        print("Restaurants:")

        SubProcess = True
        while SubProcess == True:
            try:
                count = 1
                for i in self.restaurants[:n]:
                    print(f"{count}: - {i}")
                    count+=1
                choice = input("Enter the number of the restaurant you want to see: ")
                if choice == "q":
                    SubProcess = False
                    return "q"
                elif choice == "m":
                    SubProcess = False
                    return "m"
                else:
                    choice = int(choice)
                match choice:
                    case choice if choice < 1 or choice > len(self.restaurants):
                        print("Invalid choice, please try again.")
                    case choice if type(choice) != int:
                        print("Invalid choice, please try again.")
                    case _:
                        self.restaurants[choice-1].selector()
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
                response = self.restrauntListPresenter()
                if response == "q":
                    break
                if response == "m":
                    self.display_menu()
                # print([str(x) for x in self.restaurants[:10]])
            elif choice == '2':
                self.getClosestList(input("Enter your address: "))
                response = self.restrauntListPresenter()
                if response == "q":
                    break
                if response == "m":
                    self.display_menu()
            elif choice == "3":
                for i in self.cuisines:
                    print(i)
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
        print("3. Show all Cuisines")
        print("4. Exit")
        return input("Enter choice: ")
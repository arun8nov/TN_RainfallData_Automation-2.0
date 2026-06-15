import os
import time 
from datetime import datetime
from datetime import timedelta
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings("ignore")

from scraper_utils import re_index, parse_date_from_panel, parse_rainfall_table

# Load historical data
history_df = pd.read_csv('tnRainfallData.csv', index_col=0)
history_df.date = pd.to_datetime(history_df.date)

# Create Empty DataFrame to store the values
column_Name = ['dept', 'dist', 'station', 'value', 'date']
Search_Rain_Fall_Data = pd.DataFrame(columns=column_Name)
Search_Rain_Fall_Data.index.name = 'id'

# Get date input starting from 01-01-2025
Start_Date = '01-01-2025'
End_Date = datetime.today().strftime('%d-%m-%Y')

# Change date format
sd = datetime.strptime(Start_Date, "%d-%m-%Y").date()
ed = datetime.strptime(End_Date, "%d-%m-%Y").date()

# Get all list of date between start date and end date
List_date_format = [] 
while sd <= ed:
    List_date_format.append(sd)
    sd = sd + timedelta(days=1)
    
# Filter out dates already present in history to avoid O(N^2) redundancy
existing_dates = {dt.date() for dt in history_df.date.dropna().unique()}
List_Object_format = [dt.strftime("%d-%m-%Y") for dt in List_date_format if dt not in existing_dates]

if not List_Object_format:
    print("All dates from 01-01-2025 to today are already present in the database. Nothing to scrape.")
    import sys
    sys.exit(0)

print(f"Scraping {len(List_Object_format)} missing dates...")

# Configure Chrome to run headlessly for Codespaces / Github Actions
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")

# Open the browser and enter the site 
driver = webdriver.Chrome(options=chrome_options)
driver.get("https://beta-tnsmart.rimes.int/index.php/Rainfall/daily_data")

# Get the html code from the web and looping over the date
for current_date_str in List_Object_format:  
    try:
        dropdown = driver.find_element(By.ID, "type")
        select = Select(dropdown)
        select.select_by_index(1)

        # Date selection
        date_input = driver.find_element(By.ID, "date")
        date_input.clear()
        date_input.send_keys(current_date_str)
        
        # Search the selection
        search = driver.find_element(By.NAME, "submit")
        search.click()
        time.sleep(1) # Small delay to ensure page loads
            
        html_code = driver.page_source
        soup = BeautifulSoup(html_code, 'html.parser')
        Da_panel = soup.find(class_="panel-heading")
        
        if Da_panel is not None:
            Date_parsed = parse_date_from_panel(Da_panel.text)
            df3 = parse_rainfall_table(soup, Date_parsed)
            if df3 is None:
                raise ValueError("Parsed table was empty.")
        else: 
            # No rainfall occurred in the search
            empty_row = {
                'dept': ['All'],
                'dist': ['All'],
                'station': ['All'],
                'value': [0.0],
                'date': [current_date_str]
            }
            df2 = pd.DataFrame(empty_row)
            df2['date'] = pd.to_datetime(df2['date'], format="%d-%m-%Y")
            df3 = df2
            
        Search_Rain_Fall_Data = pd.concat([Search_Rain_Fall_Data, df3])
        print(f"Scraped date: {current_date_str}")
    except Exception as e:
        print(f"Error scraping date {current_date_str}: {str(e)}")
        # Fallback to empty row on error so the loop continues
        empty_row = {
            'dept': ['All'],
            'dist': ['All'],
            'station': ['All'],
            'value': [0.0],
            'date': [current_date_str]
        }
        df2 = pd.DataFrame(empty_row)
        df2['date'] = pd.to_datetime(df2['date'], format="%d-%m-%Y")
        Search_Rain_Fall_Data = pd.concat([Search_Rain_Fall_Data, df2])
    
driver.quit()  

Search_Rain_Fall_Data = re_index(Search_Rain_Fall_Data)
final_df = pd.concat([history_df, Search_Rain_Fall_Data])
final_df = final_df.drop_duplicates()
final_df = final_df.dropna()
final_df = final_df.sort_values(by='date')
final_df = re_index(final_df)

# Save the final DataFrame to a CSV file
final_df.to_csv('tnRainfallData.csv')
print("Successfully synced data history:")
print(final_df.tail(20))

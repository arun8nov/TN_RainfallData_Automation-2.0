# Import libraries
import os
import time 
import datetime
from datetime import date
import pandas as pd
from bs4 import BeautifulSoup
import requests
import warnings
warnings.filterwarnings("ignore")

from scraper_utils import re_index, parse_date_from_panel, parse_rainfall_table

def run_daily_sync(csv_path="tnRainfallData.csv"):
    """
    Fetches today's rainfall data and syncs it into the CSV database.
    Returns: (success_bool, message_str)
    """
    try:
        if not os.path.exists(csv_path):
            return False, f"CSV file not found at {csv_path}"
            
        current_Data = pd.read_csv(csv_path, index_col=0)
        current_Data['date'] = pd.to_datetime(current_Data['date'])
        
        # Get today's data from the websource
        url = 'https://beta-tnsmart.rimes.int/index.php/Rainfall/daily_data'
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            print("The HTML file was imported successfully.")
            soup = BeautifulSoup(response.text, 'html.parser')
        else:
            return False, f"An error occurred while importing the file: HTTP {response.status_code}"
        
        Da_panel = soup.find(class_="panel-heading")
        
        if Da_panel is not None:
            print("RainFall occurred in TN")
            Date_parsed = parse_date_from_panel(Da_panel.text)
            Today_Rain_Fall = parse_rainfall_table(soup, Date_parsed)
            if Today_Rain_Fall is None:
                return False, "Failed to parse rainfall table from website HTML."
        else:
            print("No Rain Fall today")
            DL = [f"{date.today().day}-{date.today().month}-{date.today().year}"]
            Empty_table = {'dept': ['TN'], 'dist': ['All'], 'station': ['All'], 'value': [0.0], 'date': DL}
            df = pd.DataFrame(Empty_table)
            df['date'] = pd.to_datetime(df['date'], format="%d-%m-%Y")
            Today_Rain_Fall = df.copy()
        
        # Sync changes to local CSV database
        TN_Rain_Fall_History = current_Data.copy()
        TN_Rain_Fall_History['date'] = pd.to_datetime(TN_Rain_Fall_History['date'], format="%Y-%m-%d")
        
        last_history_date = TN_Rain_Fall_History['date'].iloc[-1] if not TN_Rain_Fall_History.empty else None
        today_scraped_date = Today_Rain_Fall['date'].iloc[0]
        
        if last_history_date != today_scraped_date:
            Total_Rain_Fall_Data = pd.concat([TN_Rain_Fall_History, Today_Rain_Fall])
            status_msg = f"Data Added for {today_scraped_date.strftime('%Y-%m-%d')}."
        else:
            Total_Rain_Fall_Data = TN_Rain_Fall_History.copy()
            status_msg = "No Change. Today's data is already in database."
        
        Total_Rain_Fall_Data = Total_Rain_Fall_Data.reset_index(drop=True)
        Total_Rain_Fall_Data.index.name = 'id'
        Total_Rain_Fall_Data['date'] = Total_Rain_Fall_Data['date'].dt.strftime('%Y-%m-%d')
        Total_Rain_Fall_Data = Total_Rain_Fall_Data[['dept', 'dist', 'station', 'value', 'date']]
        
        Total_Rain_Fall_Data.drop_duplicates(inplace=True)
        Total_Rain_Fall_Data.dropna(inplace=True)
        Total_Rain_Fall_Data = Total_Rain_Fall_Data.sort_values(by='date')
        Total_Rain_Fall_Data = re_index(Total_Rain_Fall_Data)
        
        # Save the DataFrame to a CSV file
        Total_Rain_Fall_Data.to_csv(csv_path)
        print("Data saved to tnRainfallData.csv")

        return True, status_msg
    except Exception as e:
        return False, f"Exception occurred: {str(e)}"

if __name__ == "__main__":
    success, message = run_daily_sync()
    print(message)
    if not success:
        import sys
        sys.exit(1)
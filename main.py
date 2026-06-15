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

        # Export today's summary to JSON for API hosting
        try:
            latest_date_str = Total_Rain_Fall_Data['date'].max()
            today_df = Total_Rain_Fall_Data[Total_Rain_Fall_Data['date'] == latest_date_str]
            
            if not today_df.empty:
                total_val = float(today_df['value'].sum())
                avg_val = float(today_df['value'].mean())
                
                dist_grouped = today_df.groupby('dist')['value'].sum()
                top_dist = dist_grouped.idxmax() if not dist_grouped.empty else "None"
                top_dist_val = float(dist_grouped.max()) if not dist_grouped.empty else 0.0
                
                # Ensure we handle multiple identical max index gracefully
                idx_max = today_df['value'].idxmax()
                max_row = today_df.loc[idx_max] if pd.notna(idx_max) else None
                if isinstance(max_row, pd.DataFrame):
                    max_row = max_row.iloc[0]
                top_station = max_row['station'] if max_row is not None else "None"
                top_station_val = float(max_row['value']) if max_row is not None else 0.0
                
                dist_breakdown = dist_grouped.round(2).to_dict()
                
                json_summary = {
                    "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "observation_date": latest_date_str,
                    "total_rainfall_mm": round(total_val, 2),
                    "average_rainfall_mm": round(avg_val, 2),
                    "top_district": {
                        "name": top_dist,
                        "value_mm": round(top_dist_val, 2)
                    },
                    "top_station": {
                        "name": top_station,
                        "value_mm": round(top_station_val, 2)
                    },
                    "district_breakdown": dist_breakdown
                }
                
                import json
                dir_name = os.path.dirname(csv_path)
                json_path = os.path.join(dir_name, "latest_rainfall.json")
                with open(json_path, "w") as f:
                    json.dump(json_summary, f, indent=4)
                print("Latest rainfall data exported to latest_rainfall.json")

                # Export as JavaScript variable to bypass browser CORS file:// restrictions
                js_path = os.path.join(dir_name, "latest_rainfall.js")
                with open(js_path, "w") as f:
                    f.write(f"const latestRainfallData = {json.dumps(json_summary, indent=4)};")
                print("Latest rainfall data exported to latest_rainfall.js")
        except Exception as e_json:
            print(f"Warning: Failed to generate latest_rainfall.json: {str(e_json)}")

        return True, status_msg
    except Exception as e:
        return False, f"Exception occurred: {str(e)}"

if __name__ == "__main__":
    success, message = run_daily_sync()
    print(message)
    if not success:
        import sys
        sys.exit(1)
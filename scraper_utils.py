import pandas as pd
from bs4 import BeautifulSoup

def re_index(df):
    df = df.reset_index(drop=True)
    df.index.name = 'id'
    return df

def parse_date_from_panel(panel_text):
    """
    Parses the date string from the panel heading text.
    E.g. 'District wise observed Rainfall\n                    data on 15-Jun-2026' -> '15-06-2026'
    """
    Date_str = panel_text.strip().replace("District wise observed Rainfall\n                    data on ", "")
    month_map = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06", 
        "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
    }
    month_abbr = Date_str[3:6]
    if month_abbr in month_map:
        Date_parsed = Date_str.replace(month_abbr, month_map[month_abbr])
    else:
        Date_parsed = Date_str
    return Date_parsed

def parse_rainfall_table(soup, date_str):
    """
    Parses the HTML table with ID 'data_table' and returns a cleaned DataFrame.
    """
    table = soup.find('table', id="data_table")
    if not table:
        return None
        
    table_tr = table.find_all('tr')
    tr_elements = table_tr[1:]
    datalist = [tr.text.strip().replace("\n\n", ",").replace("\n", ",") for tr in tr_elements]
    
    if not datalist:
        return None
        
    df1 = pd.DataFrame(datalist, columns=['A'])['A'].str.split(",", expand=True)

    # Drop the summary row at the end
    df1 = df1.drop([len(df1) - 1])
    
    # Drop columns that are completely empty
    df1 = df1.dropna(axis=1, how='all')
    
    delete_rows = df1[df1[4].isna()].index.append(df1[-1:].index)
    df1 = df1.drop(delete_rows, axis=0)
    
    if len(df1.columns) > 6:
        A = df1[[3]]
        B = df1[4].str.extract('([a-zA-Z]+)').dropna()
        C = df1[5].str.extract('([a-zA-Z]+)').dropna()
        B.loc[C.index] = B.loc[C.index] + "," + C.loc[C.index]
        D = pd.DataFrame(A.loc[B.index].values + "," + B.values, index=B.index)
        A.loc[B.index] = D
        df1[3] = A[3]
        E = df1[4].str.extract(r'(\d+\.?\d*)').dropna()
        F = df1[5].str.extract(r'(\d+\.?\d*)').dropna()
        G = df1[6].str.extract(r'(\d+\.?\d*)').dropna()
        H = pd.concat([E, F, G])
        df1[[4]] = H
    elif len(df1.columns) > 5:
        A = df1[[3]]
        B = df1[4].str.extract('([a-zA-Z]+)').dropna()
        C = pd.DataFrame(A.loc[B.index].values + "," + B.values, index=B.index)
        A.loc[B.index] = C
        df1[3] = A[3]
        E = df1[4].str.extract(r'(\d+\.?\d*)').dropna()
        F = df1[5].str.extract(r'(\d+\.?\d*)').dropna()
        H = pd.concat([E, F])
        df1[[4]] = H
        
    if len(df1.columns) > 5:
        df1 = df1.iloc[:, :5]
        
    df1 = df1.drop(columns=[0])
    column_Name = ['dept', 'dist', 'station', 'value']
    df1.columns = column_Name
    df1.value = df1.value.astype(float)
    df1 = df1.reset_index(drop=True)
    
    df1['date'] = pd.to_datetime(date_str, format="%d-%m-%Y")
    return df1

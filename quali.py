import fastf1
import pandas as pd

# 1. Setup and Enable Cache
fastf1.Cache.enable_cache('fastf1_cache') 

# 2. Get the season schedule
year = 2026
schedule = fastf1.get_event_schedule(year)

# List to temporarily store individual race dataframes
all_dfs = []

# 3. Iterate through every round
for idx, event in schedule.iterrows():
    # Only pull official grand prix weekends
    if event['EventFormat'] != 'testing':
        event_name = event['EventName']
        print(f"Loading {event_name}...")
        
        try:
            # Load qualifying session
            session = fastf1.get_session(year, event_name, 'Q')
            session.load(laps=False, telemetry=False) # Speeds up loading when you only want results
            
            # Extract results DataFrame
            df_res = session.results.copy()
            
            # Add event descriptors so you can distinguish races in the master DataFrame
            df_res['RoundNumber'] = event['RoundNumber']
            df_res['EventName'] = event_name
            
            all_dfs.append(df_res)
            
        except Exception as e:
            print(f"Skipping {event_name} due to error: {e}")
        break

# 4. Merge all sessions into one Master DataFrame
master_quali_df = pd.concat(all_dfs, ignore_index=True)

#master_quali_df.to_csv('powerbi_data/master_quali_df.csv', index=False)

# View the final dataset layout
print(master_quali_df[['RoundNumber', 'EventName', 'Position', 'Abbreviation', 'TeamName', 'Q3']].tail())

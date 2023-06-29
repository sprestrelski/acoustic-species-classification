import os
import shutil
import pandas as pd

# distribute clips to species-specific folders with ebird codes
folder_path = "/mnt/passive-acoustic-biodiversity/132_peru_xc_BC_2020"
metadata_path = "/mnt/passive-acoustic-biodiversity/132_peru_xc_BC_2020/metadata.csv"
csv = pd.read_csv(metadata_path)
ebird = pd.read_csv("/home/sprestrelski/eBird_Taxonomy_v2021.csv")

def gen_folders_from_metadata():
    for i, row in csv.iterrows():
        if (pd.isna(row['Species eBird Code'])): 
            continue
        species_folder = os.path.join(folder_path, row['Species eBird Code'])
        filepath = os.path.join(folder_path, row['filename'])
        if not os.path.exists(species_folder):
            os.makedirs(species_folder)
        if os.path.exists(filepath):
            try:
                shutil.move(filepath, os.path.join(species_folder, row['filename']))
            except: 
                print("error with ", filepath)

def gen_folders_from_filename():
    # get files in top-level only
    files = [f.path for f in os.scandir(folder_path) if f.path.split('.')[-1] == "mp3"]
    codes = dict(zip(ebird.SCI_NAME, ebird.SPECIES_CODE))
    
    for f in files:
        
if __name__ == '__main__':
    gen_folders_from_filename()

# np.unique([f.split('/')[-1].split(' - ')[1] for f in files]).size
# np.unique([" ".join(f.split('/')[-1].split(' - ')[2].split(" ")[:2]).split(".")[0] for f in files]).size
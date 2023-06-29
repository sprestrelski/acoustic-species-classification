# upsample classes with fewer than 50 samples to 50, limit classes to 500 samples
import os
import shutil
from random import shuffle
from random import choice
from math import floor

chunk_path_old = '/share/acoustic_species_id/binary_chunks/Z_no_bird'
validation_path = '/share/acoustic_species_id/binary_chunks/validation/no_bird'

filetype = "wav"

def split():
    s = chunk_path_old
    files = [f.path.split('/')[-1] for f in os.scandir(s) if f.path.endswith(filetype)]
    shuffle(files)
    validation = files[int(.2*len(files)):]

    for file in validation:
        shutil.move(os.path.join(s, file), os.path.join(validation_path, file.split('/')[-1]))
        
            
if __name__ == '__main__':
    split()
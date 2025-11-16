#First Step: Preprocess EEG Data
python Scripts/preprocess.py \       
  --vhdr sub-01/ses-01/eeg/sub-01_ses-01_task-visual_eeg.vhdr \
  --out_dir outputs/sub-01

#Second Strp: Run Visualization Script
python Scripts/raw_visuals.py


#donot forget to change the paths according to your data organization!
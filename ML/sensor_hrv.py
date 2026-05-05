from operator import le
import heartpy as hp
import pandas as pd
import numpy as np
import joblib
import time
import csv
from datetime import datetime  

# HRV extraction from PPG sensor using HeartPy
def get_hrv_from_ppg(ppg_signal, sample_rate=100):
    try:
        working_data, measures = hp.process(
            ppg_signal,
            sample_rate=sample_rate,
            clean_rr=True
        )
        return measures.get('rmssd', None)
    except Exception as e:
        print("HeartPy error:", e)
        return None

# Example simulation of PPG (Not real sensor data) 
def get_example_ppg():
    sample_rate = 100
    duration = 10  # seconds
    
    t = np.linspace(0, duration, sample_rate * duration)
    
    # simulate heartbeat peaks (sharper waveform)
    signal = np.sin(2 * np.pi * 1.2 * t)
    signal = np.maximum(signal, 0)  # only peaks
    
    # small noise
    noise = 0.01 * np.random.randn(len(t))
    return signal + noise

# Load ML Model
model, le = joblib.load("model.pkl")
print("Model loaded successfully")

# Example User Profile (Simulated Input)
user_profile = {
    "age": 22,
    "sex": 1, # 0 = female, 1 = male
    "bmi": 24.5
}

# Stress score from 1-10
def stress_score_from_label(label):
    if label == "low_stress":
        return 2
    elif label == "medium_stress":
        return 5
    else:
        return 8

# Convert scores to level
def stress_level(score):
    if score <= 3:
        return "LOW"
    elif score <= 7:
        return "MODERATE"
    else:
        return "HIGH"
    
# Stress messages
def stress_message(level):
    if level == "HIGH":
        return "Quickly take a break"
    elif level == "MODERATE":
        return "Stay focused and take care of yourself"
    else:
        return "You are doing well"
    
# Display results
def update_display(hrv, score, level, message):
    print(f"HRV: {hrv} ms")
    print(f"Stress Score: {score}/10")
    print(f"Level: {level}")
    print(message)

recent_scores = []

# Real-time loop (SIMULATION)
print("\nStarting PAIGE...\n")

try:
    while True:
        # get sensor data (replace later with MAX30102 sensor code)
        ppg_signal = get_example_ppg() 

        # Extract HRV 
        hrv = get_hrv_from_ppg(ppg_signal)

        if hrv is None:
            print("Signal too noisy or processing failed, retrying...")
            time.sleep(1)
            continue

        hrv = round(hrv, 2) 

        features = pd.DataFrame([{
            "age": user_profile['age'], 
            "sex": user_profile['sex'], 
            "bmi": user_profile['bmi'],
        }])  

        pred_encoded = model.predict(features)[0]
        pred_label = le.inverse_transform([pred_encoded])[0]

        # Logic to use the average of recent predictions - to smooth out the results 
        # Convert to score and level
        score = stress_score_from_label(pred_label)

        # Smooth results to not get unstable readings - average of last 5 scores
        recent_scores.append(score)

        # Keep only last 5 values 
        if len(recent_scores) > 5:
            recent_scores.pop(0)

        # Average score 
        avg_score = sum(recent_scores) / len(recent_scores)

        # Use smoothed score to determine level and message
        level = stress_level(avg_score)
        message = stress_message(level)
        
        # Display results
        update_display(hrv, score, level, message)
        
        # Log results to CSV
        with open("stress_log.csv", "a", newline="") as f: 
            writer = csv.writer(f) 
            writer.writerow([datetime.now(), hrv, pred_label, avg_score, level])

        time.sleep(2)

except KeyboardInterrupt:
    print("\nSession ended.")
    if recent_scores:
        print(f"Final smoothed score: {sum(recent_scores)/len(recent_scores):.1f}/10")


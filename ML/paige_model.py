import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report

# Load the datasets
train = pd.read_csv("Datasets/train.csv")
test = pd.read_csv("Datasets/test.csv")
googleFit = pd.read_csv("Datasets/hamon_googlefit_medical_realistic.csv")

# Use SWELL to learn RMSSD and stress thresholds
swell = pd.concat([train, test])[['RMSSD', 'condition']].dropna()

rmssd_by_condition = swell.groupby('condition')['RMSSD'].median()
print("Median RMSSD per stress condition (from SWELL):")
print(rmssd_by_condition.sort_values())

googleFit_reduced = googleFit[['age','sex', 'bmi', 'hrv']].dropna()

print("\nGoogle Fit HRV distribution:")
print(googleFit_reduced['hrv'].describe())

low_threshold  = googleFit_reduced['hrv'].quantile(0.3) 
high_threshold = googleFit_reduced['hrv'].quantile(0.7)   

print(f"\nSWELL-informed HRV thresholds for Google Fit data:")
print(f"  HRV < {low_threshold:.1f}  → high_stress  (bottom 30%)")
print(f"  HRV < {high_threshold:.1f}  → medium_stress (middle 40%)")
print(f"  HRV >= {high_threshold:.1f} → low_stress   (top 30%)")

def stress_label_from_swell(hrv):
    if hrv < low_threshold:
        return "high_stress"
    elif hrv < high_threshold:
        return "medium_stress"
    else:
        return "low_stress"

fit_reduced = googleFit_reduced.copy()
fit_reduced['stress'] = fit_reduced['hrv'].apply(stress_label_from_swell)

print(fit_reduced.dtypes)
print(fit_reduced.head())

print("\nGoogle Fit stress label distribution:")
print(fit_reduced['stress'].value_counts())

# Encode 'sex' if it's a string (e.g. 'M'/'F' or 'male'/'female')
if fit_reduced['sex'].dtype == object:
    fit_reduced['sex'] = LabelEncoder().fit_transform(fit_reduced['sex'])
    print("Encoded 'sex' column to numeric")

print("\nfit_reduced dtypes:")
print(fit_reduced.dtypes)
print("\nSample rows:")
print(fit_reduced.head())

# Train Google Fit real-world features 
# Features and labels
X = fit_reduced[['age', 'sex', 'bmi']]
Y = fit_reduced['stress']

X_train, X_test, y_train, y_test = train_test_split(X, Y, test_size=0.2, random_state=42)

le = LabelEncoder()
y_train_enc = le.fit_transform(y_train)
y_test_enc  = le.transform(y_test)

print(f"\nX_train: {X_train.shape}, y_train: {y_train_enc.shape}")
print(f"X_test:  {X_test.shape},  y_test:  {y_test_enc.shape}")

model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
model.fit(X_train, y_train_enc)

# Evaluate the model
# Model's accuracy is 0.826 = about 83% correct predictions  
y_pred = model.predict(X_test)
print("Accuracy: ", accuracy_score(y_test_enc, y_pred))
print("\n Detailed Report: ")
print(classification_report(y_test_enc, y_pred, target_names=le.classes_))

# Feature importance
importances = pd.Series(model.feature_importances_, index=['age', 'sex', 'bmi'])
print("\nFeature Importances:")
print(importances.sort_values(ascending=False))

# Save model
joblib.dump((model, le), "model.pkl")
print("Model trained and saved as model.pkl")

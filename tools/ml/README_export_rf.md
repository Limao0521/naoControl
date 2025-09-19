Exporting RandomForest models for NAO (no scikit-learn on robot)

This workspace includes a helper script `export_rf_to_npz.py` that converts
scikit-learn RandomForestRegressor objects and StandardScaler into NPZ files
that can be loaded by `robot_scripts/adaptive_walk_randomforest.py` without
having scikit-learn installed on NAO.

Steps (on your host PC with scikit-learn/joblib):

1. Train your RandomForestRegressor(s) and StandardScaler as usual. You may
   have one regressor per gait parameter (StepHeight, MaxStepX, ...), or a
   single model mapping features -> multiple outputs.

2. Save your models using joblib.dump:

   joblib.dump(model, 'models/randomforest_model_<param>.pkl')
   joblib.dump(scaler, 'models/feature_scaler.pkl')

3. Run the exporter to produce NPZ files compatible with the NAO loader:

   python tools/export_rf_to_npz.py --model models/randomforest_model_<param>.pkl --scaler models/feature_scaler.pkl --out-dir models

   The exporter will create:
     - models/randomforest_model_<param>.npz  (contains key 'forest' with tree dicts)
     - models/feature_scaler.npz              (contains 'mean' and 'scale')

4. Copy the `models/` directory to the NAO (e.g., via scp). Place it in the
   same folder where `adaptive_walk_randomforest.py` will look (default: ./models).

5. On the NAO, run `adaptive_walk_randomforest.py` (Python 2.7). The script will
   detect the NPZ files and use a pure-numpy/pure-Python tree evaluator to run
   inference without scikit-learn.

Notes:
- The exporter currently saves the forest as a single NPZ with key 'forest'
  containing an object-array of dicts. The loader supports this format.
- If you prefer to ship joblib PKL files, you can still install scikit-learn
  on the NAO (requires building wheels for cp27/i686). See the project docs
  for Docker manylinux build steps.

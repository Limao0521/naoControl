#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script to verify AdaptiveWalkLightGBM golden_csv_path fix
"""
import sys
import os

# Add robot_scripts to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'robot_scripts'))

try:
    from adaptive_walk_lightgbm_nao import AdaptiveWalkLightGBM
    print("[INFO] Successfully imported AdaptiveWalkLightGBM")
    
    # Test instantiation
    print("[INFO] Testing AdaptiveWalkLightGBM instantiation...")
    adaptive_walk = AdaptiveWalkLightGBM(models_dir="models_npz_automl", mode="production")
    print("[SUCCESS] AdaptiveWalkLightGBM instantiated successfully!")
    print("[INFO] Golden CSV path: {}".format(adaptive_walk.golden_csv_path))
    print("[INFO] Models directory: {}".format(adaptive_walk.models_dir))
    print("[INFO] Mode: {}".format(adaptive_walk.mode))
    
except ImportError as e:
    print("[ERROR] Import failed: {}".format(e))
except AttributeError as e:
    print("[ERROR] Attribute error (golden_csv_path issue?): {}".format(e))
except Exception as e:
    print("[ERROR] Unexpected error: {}".format(e))
    import traceback
    traceback.print_exc()

"""
Pytest configuration for core tests.

This file ensures that the tjbot package can be imported correctly
when running pytest from any location.
"""
import sys
import os

# Add the src directory to the path so tjbot can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

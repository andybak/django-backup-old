import os
import sys

# Add internal apps to python path.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..', '..')))

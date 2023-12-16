import sys
import os
import time

import logging

# Set the desired logging level (e.g., logging.DEBUG, logging.INFO, logging.WARNING, etc.)
logging.basicConfig(level=logging.INFO)

# Get the current script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add the library path to sys.path
library_path = os.path.join(script_dir, "./pyImpinj")
sys.path.insert(0, library_path)

import queue
from pyImpinj import ImpinjR2KReader

TAG_QUEUE = queue.Queue( 1024 )
R2000 = ImpinjR2KReader( TAG_QUEUE, address=1 )
R2000.connect( '/dev/ttyUSB0' )

R2000.worker_start()

# R2000.rt_inventory( repeat=100 )
print("\n\tTEMP")
R2000.temperature()

for i in range(4):
    print(f"\tSet work antenna {i}")
    R2000.set_work_antenna(antenna=i)

    print("\tSet ant connection detector")
    R2000.set_ant_connection_detector(loss=10)

    print("\t get rf port return loss")
    print(R2000.get_rf_port_return_loss())

    R2000.set_ant_connection_detector(0)

print("\n\tSet default antenna")
R2000.set_work_antenna(antenna=0)

print("\n\tGet frequency region")
print(R2000.get_frequency_region())

print("\n\tInventory")
R2000.inventory()

print("\n\tGet inventory buffer tag count")
R2000.get_inventory_buffer_tag_count()
print(R2000.get_inventory_buffer())
# print( TAG_QUEUE.get( ) )
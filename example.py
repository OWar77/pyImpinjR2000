import sys
import os
import time
import signal

import logging

import queue
from pyImpinj import ImpinjR2KReader

# Set the desired logging level (e.g., logging.DEBUG, logging.INFO, logging.WARNING, etc.)
logging.basicConfig(level=logging.WARNING)

# Get the current script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add the library path to sys.path
library_path = os.path.join(script_dir, "./pyImpinj")
sys.path.insert(0, library_path)

TAG_QUEUE = queue.Queue( 1024 )
R2000 = ImpinjR2KReader( TAG_QUEUE, address=1 )

R2000.connect()

R2000.worker_start()

exit_required = False

def signal_handler(sig, frame):
    print("\nCtrl+C pressed. Exiting...")
    # Perform cleanup or additional actions before exiting
    global exit_required
    exit_required = True

# Register the signal handler for Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

# R2000.temperature()

# print(R2000.scan_connected_antenna())

# print(R2000.get_frequency_region())

# R2000.inventory()

# R2000.get_inventory_buffer_tag_count()
# print(R2000.get_inventory_buffer())
#print( TAG_QUEUE.get( ) )
time_start = time.time()

while(exit_required == False):
    # R2000.fast_power( 22)
    # R2000.set_rf_power(antenna1=20, antenna2=0, antenna3=0, antenna4=0)
    count = R2000.inventory( repeat=2 )
    #count = R2000.get_inventory_buffer_tag_count()
    tags = R2000.get_and_reset_inventory_buffer( count )
    # print(tags)
    print(f"\ntime: {time.time() - time_start}s")
    for tag in tags:
        print(f"tag: {int(tag[2])} dist: {R2000.distance(tag[1])}")
    time.sleep(0.3)
    
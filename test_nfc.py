#from mfrc522 import SimpleMFRC522 

# tests the NFC reader by itself 

#reader = SimpleMFRC522()
#print("Tap a card")
#uid = reader.read_id() #waits until a card is tapped
#print("Card UID:", uid)

import time

import board
import busio
from adafruit_pn532.i2c import PN532_I2C

# tests the PN532 NFC reader by itself (I2C mode)
# DIP switch on the reader: 1 = ON, 2 = OFF
i2c = busio.I2C(board.SCL, board.SDA)
reader = PN532_I2C(i2c)

ic, ver, rev, support = reader.firmware_version
print("Found PN532, firmware", ver, rev)

reader.SAM_configuration()
print("Tap a card (Ctrl+C to stop)")

while True:
    uid = reader.read_passive_target(timeout=0.5) #waits for a card
    if uid is not None:
        print("Card UID:", uid.hex().upper())
        time.sleep(1) #so one tap is not printed many times
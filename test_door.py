import Rpi.GPIO as GPIO 
import time 
# tests the magnetic door switch by itself
#move magnet near/away from switch
GPIO.setmode(GPIO.BOARD) 
#pin reads High normally,
#Low when magnet closes switch

GPIO.setup(29, GPIO.IN, pull_up_down=GPIO.PUD_UP)

while True:
    if GPIO.input(29) == GPIO.LOW: #magnet is nearby
        print("Door is closed")
    else:
        print("Door is open")
    time.sleep(1) #for one second
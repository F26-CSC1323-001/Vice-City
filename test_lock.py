import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD) #pin numbers
GPIO.setup(11, GPIO.OUT, initial=GPIO.HIGH) #pin 11

GPIO.output(11, GPIO.LOW) #lock opens 
print("Relay ON") 
time.sleep(3) # opens for 3 seconds
GPIO.output(11, GPIO.HIGH) #lock closes
GPIO.cleanup()
import atexit
import threading
import time

# these libraries only exist on the Pi, so on a laptop this file runs in
# fake mode and just prints what it would have done
try:
    import RPi.GPIO as GPIO
    import board
    import busio
    from adafruit_pn532.i2c import PN532_I2C

    FAKE_MODE = False

except (ImportError, RuntimeError) as error:
    FAKE_MODE = True
    print("hardware.py is in FAKE MODE:", error)


# the only locker with a real lock, the other lockers stay simulated
REAL_LOCKER = 1


# the numbers printed on the breadboard adapter (gp17 and gp5)
# these are not the same as the physical pin numbers in test_lock.py
RELAY_PIN = 17
DOOR_PIN = 5


# how long the lock gets power each time it opens
# the lock burns out if it stays powered, so keep this to a few seconds
UNLOCK_SECONDS = 3


# rest time after opening, so repeated presses cannot overheat the lock
COOLDOWN_SECONDS = 5


# how often the door sensor gets checked
DOOR_CHECK_SECONDS = 0.5


# the card fake mode pretends was tapped
FAKE_CARD_UID = "CARD001"


relay_busy = threading.Lock()
reader_busy = threading.Lock()
reader = None


# sets up the pins and the reader, then starts watching the door
# on_door_change gets called with "open" or "closed"
def start(on_door_change):
    global reader

    if FAKE_MODE:
        return

    GPIO.setmode(GPIO.BCM)

    # the relay is off while its pin is HIGH
    GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(DOOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    atexit.register(stop)

    # the lock and door still work if the reader is not found
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        reader = PN532_I2C(i2c)
        reader.SAM_configuration()
    except (ValueError, RuntimeError, OSError) as error:
        reader = None
        print("NFC reader not found:", error)

    threading.Thread(
        target=watch_door,
        args=(on_door_change,),
        daemon=True
    ).start()


# leaves the lock off when the program ends
def stop():
    set_relay(False)
    GPIO.cleanup()


# turns the relay on or off
def set_relay(on):
    if FAKE_MODE:
        print("FAKE: relay", "on" if on else "off")
    elif on:
        GPIO.output(RELAY_PIN, GPIO.LOW)
    else:
        GPIO.output(RELAY_PIN, GPIO.HIGH)


# opens a locker, does nothing for the simulated lockers
def unlock(locker_number):
    if locker_number != REAL_LOCKER:
        return

    # runs in the background so the web page does not have to wait
    threading.Thread(target=pulse_relay, daemon=True).start()


# powers the lock for a few seconds, then always turns it back off
def pulse_relay():

    # if the lock is already opening or resting, this press does nothing
    if not relay_busy.acquire(blocking=False):
        return

    try:
        try:
            set_relay(True)
            time.sleep(UNLOCK_SECONDS)
        finally:
            set_relay(False)

        time.sleep(COOLDOWN_SECONDS)
    finally:
        relay_busy.release()


# returns "open" or "closed"
def read_door():
    if FAKE_MODE:
        return "closed"

    # the pin reads LOW when the magnet is next to the sensor
    if GPIO.input(DOOR_PIN) == GPIO.LOW:
        return "closed"

    return "open"


# runs in the background and reports each time the door changes
def watch_door(on_door_change):
    last_status = None

    while True:
        status = read_door()

        if status != last_status:

            # if the update fails, the next check tries it again
            try:
                on_door_change(status)
                last_status = status
            except Exception as error:
                print("Door update failed:", error)

        time.sleep(DOOR_CHECK_SECONDS)


# tells the app whether cards can be read
def reader_ready():
    return FAKE_MODE or reader is not None


# waits for a card and returns its UID, or None if no card was tapped
def wait_for_card(seconds=2):
    if FAKE_MODE:
        time.sleep(min(seconds, 2))
        return FAKE_CARD_UID

    if reader is None:
        return None

    end_time = time.time() + seconds

    with reader_busy:
        while time.time() < end_time:

            # the reader raises several error types, a bad read just counts
            # as no card and the caller can try again
            try:
                uid = reader.read_passive_target(timeout=0.5)
            except Exception as error:
                print("Card read failed:", error)
                time.sleep(0.5)
                return None

            if uid is not None:
                return uid.hex().upper()

    return None

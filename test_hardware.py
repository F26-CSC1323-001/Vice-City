import time

import hardware

# tests the relay, door sensor and NFC reader together using hardware.py
# keep the 12V adapter unplugged for this test


def door_changed(status):
    print("Door is now", status)


print("Fake mode:", hardware.FAKE_MODE)
hardware.start(door_changed)

print("Relay should click on now, then off after", hardware.UNLOCK_SECONDS, "seconds")
hardware.unlock(hardware.REAL_LOCKER)
time.sleep(hardware.UNLOCK_SECONDS + 1)

print("Move the magnet or tap a card (Ctrl+C to stop)")

while True:
    uid = hardware.wait_for_card()
    if uid is not None:
        print("Card UID:", uid)
        time.sleep(1) #so one tap is not printed many times
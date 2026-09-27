-- stores the users of the locker system
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    pin_hash TEXT NOT NULL
);

-- stores each locker and its current state
CREATE TABLE lockers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    locker_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'available',
    door_status TEXT NOT NULL DEFAULT 'closed',
    lock_status TEXT NOT NULL DEFAULT 'locked'
);

-- keeps track of who rented which locker and for how long
CREATE TABLE rentals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    locker_id INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    amount_paid REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (locker_id) REFERENCES lockers(id)
);

-- demo cards can be used to test payments
CREATE TABLE demo_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_uid TEXT NOT NULL UNIQUE,
    balance REAL NOT NULL DEFAULT 25.00
);
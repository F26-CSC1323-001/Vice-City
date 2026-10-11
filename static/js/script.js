// Helper functions to select HTML elements easily
function getElement(selector) {
  return document.querySelector(selector);
}

function getAllElements(selector) {
  return Array.from(document.querySelectorAll(selector));
}

// Store available duration options [Name, Price, Minutes, Name used by the server]
const DURATIONS = [
  ["30 minutes", "$2.00", 30, "30min"],
  ["1 hour", "$3.00", 60, "1hour"],
  ["2 hours", "$5.00", 120, "2hours"],
  ["4 hours", "$8.00", 240, "4hours"],
  ["All day", "$12.00", 1440, "allday"]
];

// The demo card used for every payment (same card that seed_db.py creates)
const DEMO_CARD_UID = "CARD001";

// Helper to get price string by duration name
function getPrice(durationName) {
  for (let i = 0; i < DURATIONS.length; i = i + 1) {
    if (DURATIONS[i][0] === durationName) {
      return DURATIONS[i][1];
    }
  }
  return "$0.00";
}

// Helper to get minutes by duration name
function getMinutes(durationName) {
  for (let i = 0; i < DURATIONS.length; i = i + 1) {
    if (DURATIONS[i][0] === durationName) {
      return DURATIONS[i][2];
    }
  }
  return 0;
}

// Helper to get the name the back end expects (for example "1hour")
function getServerName(durationName) {
  for (let i = 0; i < DURATIONS.length; i = i + 1) {
    if (DURATIONS[i][0] === durationName) {
      return DURATIONS[i][3];
    }
  }
  return "";
}

// Application State Object
const state = {
  screen: "welcome",
  selectedLockerId: null,
  duration: "1 hour",
  extendDuration: "1 hour",
  contactedAdmin: false,
  forgotMessage: "",
  now: Date.now(),
  name: "",
  phone: "",
  pin: "",
  adminPin: "",
  rental: null, // the customer's current rental: { id, end, unlocked }
  lockers: [] // filled in with real data from the back end
};

let timerTimeout = null;

// ---------- Talking to the back end ----------

// Sends a request to the back end and gives back { ok, data }
async function callServer(path, method, body) {
  try {
    const options = { method: method };
    if (body) {
      options.headers = { "Content-Type": "application/json" };
      options.body = JSON.stringify(body);
    }
    const response = await fetch(path, options);
    const data = await response.json();
    return { ok: response.ok, data: data };
  } catch (error) {
    return { ok: false, data: { error: "Could not reach the server. Is app.py running?" } };
  }
}

// Shows a pop-up message at the top of the screen for 4 seconds
let toastTimeout = null;

function showMessage(text) {
  const toast = getElement("#toast");
  toast.textContent = text;
  toast.hidden = false;

  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(function() {
    toast.hidden = true;
  }, 4000);
}

// Shows the error message that the back end sent
function showError(result) {
  showMessage(result.data.error || "Something went wrong");
}

// The back end sends times like "2026-10-10T14:30:00.123456" - this turns them into a number
function parseServerTime(text) {
  return new Date(text.split(".")[0]).getTime();
}

// Keeps only the digits of a phone number so "318-555-1234" and "3185551234" match
function cleanPhone(text) {
  return text.replace(/\D/g, "");
}

// Path used to load the lockers for the administrator
function adminLockersPath() {
  return "/admin/lockers?admin_pin=" + encodeURIComponent(state.adminPin);
}

// Turns the locker rows from the back end into the objects this file uses
function setLockers(rows) {
  state.lockers = [];
  for (let i = 0; i < rows.length; i = i + 1) {
    const row = rows[i];
    let endTime = null;
    if (row.end_time) {
      endTime = parseServerTime(row.end_time);
    }
    state.lockers.push({
      id: String(row.locker_number),
      status: row.status,
      unlocked: row.lock_status === "unlocked",
      doorOpen: row.door_status === "open",
      end: endTime
    });
  }
}

// Loads the lockers from the back end and refreshes the screen
async function loadLockers(path, showErrors) {
  const result = await callServer(path, "GET");
  if (!result.ok) {
    if (showErrors) {
      showError(result);
    }
    return;
  }
  setLockers(result.data);
  render();
}

// Helper to find a locker object by ID
function findLocker(id) {
  for (let i = 0; i < state.lockers.length; i = i + 1) {
    if (state.lockers[i].id === id) {
      return state.lockers[i];
    }
  }
  return null;
}

// Check if a locker is currently occupied
function isLockerBusy(locker) {
  return locker.status === "occupied";
}

// Check if a locker is available for rent
function isLockerFree(locker) {
  return locker.status === "available";
}

// Check if a locker was disabled by the administrator
function isLockerOff(locker) {
  return locker.status === "disabled";
}

// Check if a rental ran out of time but the locker is still occupied
function isLockerOverdue(locker) {
  return locker.status === "occupied" && locker.end !== null && locker.end <= state.now;
}

// Calculate remaining time in minutes
function getMinutesLeft(locker) {
  if (locker.end === null) {
    return 0;
  }
  const diffInMs = locker.end - state.now;
  const remainingMins = Math.ceil(diffInMs / 60000);
  if (remainingMins < 0) {
    return 0;
  }
  return remainingMins;
}

// Format timestamp into readable time (e.g., 2:30 PM)
function formatTime(timestamp) {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

// The locker the customer is currently renting
function getActiveLocker() {
  return state.rental;
}

// Update text content safely
function setText(selector, value) {
  const element = getElement(selector);
  if (element) {
    element.textContent = value;
  }
}

// Build HTML for duration selection buttons
function buildDurationButtons(currentSelection, actionName) {
  let html = "";
  for (let i = 0; i < DURATIONS.length; i = i + 1) {
    const name = DURATIONS[i][0];
    const priceText = DURATIONS[i][1];

    let buttonClass = "btn dur ";
    if (name === currentSelection) {
      buttonClass = buttonClass + "primary";
    } else {
      buttonClass = buttonClass + "secondary";
    }

    if (name === "All day") {
      buttonClass = buttonClass + " span2";
    }

    let priceClass = "bright";
    if (name === currentSelection) {
      priceClass = "dim";
    }

    html = html + '<button class="' + buttonClass + '" data-act="' + actionName + '" data-d="' + name + '">';
    html = html + '<span>' + name + '</span>';
    html = html + '<span class="' + priceClass + '">' + priceText + '</span>';
    html = html + '</button>';
  }
  return html;
}

// Build HTML for administrator locker card
function buildAdminCard(locker) {
  let label = "Available";
  let tagClass = "ok";

  if (isLockerOff(locker)) {
    label = "Disabled";
    tagClass = "danger";
  } else if (isLockerOverdue(locker)) {
    label = "Overdue";
    tagClass = "danger";
  } else if (isLockerBusy(locker)) {
    label = "Occupied";
    tagClass = "warn";
  }

  let doorStatus = "Door closed";
  if (locker.doorOpen) {
    doorStatus = "Door open";
  }

  let rentalStatus = "No rental";
  if (isLockerOff(locker)) {
    rentalStatus = "Offline";
  } else if (isLockerOverdue(locker)) {
    rentalStatus = "Time is up";
  } else if (isLockerBusy(locker)) {
    rentalStatus = getMinutesLeft(locker) + "m left";
  }

  // the back end can unlock a locker, but it locks itself when the door closes
  let unlockBtnText = "Unlock";
  let unlockDisabledAttr = "";
  if (locker.unlocked) {
    unlockBtnText = "Unlocked";
    unlockDisabledAttr = "disabled";
  }
  if (isLockerOff(locker)) {
    unlockDisabledAttr = "disabled";
  }

  let endDisabledAttr = "";
  if (!isLockerBusy(locker)) {
    endDisabledAttr = "disabled";
  }

  // a locker that is being rented cannot be disabled
  let offBtnText = "Disable";
  let offBtnClass = "warn";
  let offDisabledAttr = "";
  if (isLockerOff(locker)) {
    offBtnText = "Enable";
    offBtnClass = "secondary";
  } else if (isLockerBusy(locker)) {
    offDisabledAttr = "disabled";
  }

  let html = '<div class="acard">';
  html = html + '<div class="row"><b class="body">Locker ' + locker.id + '</b><span class="tag ' + tagClass + '">' + label + '</span></div>';
  html = html + '<div class="stat"><div>' + doorStatus + '</div><div>' + rentalStatus + '</div></div>';
  html = html + '<div class="acts">';
  html = html + '<button class="btn secondary sm" data-act="door" data-id="' + locker.id + '" ' + unlockDisabledAttr + '>' + unlockBtnText + '</button>';
  html = html + '<button class="btn danger sm" data-act="end" data-id="' + locker.id + '" ' + endDisabledAttr + '>End</button>';
  html = html + '<button class="btn ' + offBtnClass + ' sm" data-act="off" data-id="' + locker.id + '" ' + offDisabledAttr + '>' + offBtnText + '</button>';
  html = html + '</div></div>';

  return html;
}

// Main function to update UI according to current state
function render() {
  state.now = Date.now();
  const selectedLocker = findLocker(state.selectedLockerId);

  if (state.screen === "choose-locker") {
    let availableLockers = [];
    let occupiedLockers = [];

    for (let i = 0; i < state.lockers.length; i = i + 1) {
      if (isLockerFree(state.lockers[i])) {
        availableLockers.push(state.lockers[i]);
      }
      // only lockers whose time is still running count towards "earliest availability"
      if (isLockerBusy(state.lockers[i]) && state.lockers[i].end !== null && state.lockers[i].end > state.now) {
        occupiedLockers.push(state.lockers[i]);
      }
    }

    if (availableLockers.length > 0) {
      setText("#chooseTitle", "Choose a Locker");
    } else {
      setText("#chooseTitle", "No Lockers Available");
    }

    getElement("#chooseOk").hidden = (availableLockers.length === 0);
    getElement("#chooseNone").hidden = (availableLockers.length > 0);

    let lockerPlural = " lockers ready for rental";
    if (availableLockers.length === 1) {
      lockerPlural = " locker ready for rental";
    }
    setText("#availCount", availableLockers.length + lockerPlural);

    let gridHtml = "";
    let isSelectedAvailable = false;

    for (let i = 0; i < availableLockers.length; i = i + 1) {
      const l = availableLockers[i];
      let cardClass = "card";
      let tickHtml = "";

      if (state.selectedLockerId === l.id) {
        cardClass = cardClass + " sel";
        tickHtml = '<span class="tick"><svg class="ic"><use href="#i-check"/></svg></span>';
        isSelectedAvailable = true;
      }

      gridHtml = gridHtml + '<button class="' + cardClass + '" data-act="pick" data-id="' + l.id + '">';
      gridHtml = gridHtml + '<div class="row"><b class="ct">Locker ' + l.id + '</b>' + tickHtml + '</div>';
      gridHtml = gridHtml + '<span class="pill sm"><i></i>Available</span></button>';
    }

    getElement("#lockerGrid").innerHTML = gridHtml;
    getElement("#chooseNext").disabled = !isSelectedAvailable;

    if (occupiedLockers.length > 0) {
      getElement("#earliestBox").hidden = false;
      let minMinutes = getMinutesLeft(occupiedLockers[0]);
      for (let i = 1; i < occupiedLockers.length; i = i + 1) {
        const minsLeft = getMinutesLeft(occupiedLockers[i]);
        if (minsLeft < minMinutes) {
          minMinutes = minsLeft;
        }
      }
      setText("#earliest", minMinutes + " min");
      setText("#earliestAt", "approx. " + formatTime(state.now + minMinutes * 60000));
    } else {
      getElement("#earliestBox").hidden = true;
    }
  }

  if (state.screen === "details") {
    if (selectedLocker !== null) {
      setText("#detailsLocker", "Locker " + selectedLocker.id);
      getElement("#detailsLocker").hidden = false;
    } else {
      setText("#detailsLocker", "");
      getElement("#detailsLocker").hidden = true;
    }
  }

  if (state.screen === "duration") {
    getElement("#durations").innerHTML = buildDurationButtons(state.duration, "dur");
    setText("#total", getPrice(state.duration));
  }

  if (state.screen === "payment") {
    setText("#payTotal", getPrice(state.duration));
  }

  if (state.screen === "success") {
    setText("#sTitle", "Locker " + state.rental.id + " is open");
    setText("#sEnd", formatTime(state.rental.end));
    setText("#sDur", state.duration);
  }

  if (state.screen === "rental") {
    const locker = getActiveLocker();
    const minutesLeft = getMinutesLeft(locker);
    const hours = Math.floor(minutesLeft / 60);
    const minsRem = minutesLeft % 60;

    let timeText = minsRem + "m";
    if (hours > 0) {
      timeText = hours + "h " + timeText;
    }

    let statusText = "Rental active";
    if (locker.unlocked) {
      statusText = "Door unlocked";
    }

    setText("#rTitle", "Locker " + locker.id);
    setText("#rBadge", statusText);
    setText("#rTime", timeText);
    setText("#rEnd", formatTime(locker.end));
  }

  if (state.screen === "extend") {
    const locker = getActiveLocker();
    setText("#extBadge", "Locker " + locker.id);
    getElement("#extDurations").innerHTML = buildDurationButtons(state.extendDuration, "ext");
    setText("#extTotal", getPrice(state.extendDuration));
  }

  if (state.screen === "extend-payment") {
    const locker = getActiveLocker();
    setText("#exPayTotal", getPrice(state.extendDuration));
    setText("#exPayNote", "Adding " + state.extendDuration + " to Locker " + locker.id);
  }

  if (state.screen === "forgot") {
    if (state.contactedAdmin) {
      setText("#forgotText", state.forgotMessage);
      setText("#contactBtn", "Request Sent");
    } else {
      setText("#forgotText", "Please contact the administrator for help.");
      setText("#contactBtn", "Contact Admin");
    }
  }

  if (state.screen === "admin") {
    let freeCount = 0;
    let cardsHtml = "";

    for (let i = 0; i < state.lockers.length; i = i + 1) {
      if (isLockerFree(state.lockers[i])) {
        freeCount = freeCount + 1;
      }
      cardsHtml = cardsHtml + buildAdminCard(state.lockers[i]);
    }

    setText("#adminCount", freeCount + " of " + state.lockers.length + " available");
    getElement("#adminGrid").innerHTML = cardsHtml;
  }
}

// Sends the new rental to the back end (called after the "tap your card" screen)
async function submitRental() {
  const result = await callServer("/rent", "POST", {
    name: state.name,
    phone: state.phone,
    pin: state.pin,
    duration: getServerName(state.duration),
    card_uid: DEMO_CARD_UID,
    locker_number: Number(state.selectedLockerId)
  });

  // the person may have pressed Home while we were waiting
  if (state.screen !== "payment") {
    return;
  }

  if (!result.ok) {
    showError(result);

    // if the locker was taken by someone else, let the customer pick again
    if (result.data.error === "That locker is no longer available") {
      goToScreen("choose-locker");
    } else {
      goToScreen("details");
    }
    return;
  }

  state.rental = {
    id: String(result.data.locker_number),
    end: parseServerTime(result.data.end_time),
    unlocked: true
  };
  goToScreen("success");
}

// Sends the extra time to the back end (called after the extension "tap your card" screen)
async function submitExtension() {
  const result = await callServer("/extend-rental", "POST", {
    phone: state.phone,
    pin: state.pin,
    duration: getServerName(state.extendDuration),
    card_uid: DEMO_CARD_UID
  });

  if (state.screen !== "extend-payment") {
    return;
  }

  if (!result.ok) {
    showError(result);
    goToScreen("extend");
    return;
  }

  state.rental.end = parseServerTime(result.data.new_end_time);
  goToScreen("rental");
}

// Function to handle switching screens
function goToScreen(screenName) {
  clearTimeout(timerTimeout);
  state.screen = screenName;
  hideKeyboard();

  const screens = getAllElements(".screen");
  for (let i = 0; i < screens.length; i = i + 1) {
    if (screens[i].dataset.screen === screenName) {
      screens[i].classList.add("active");
    } else {
      screens[i].classList.remove("active");
    }
  }

  if (screenName === "welcome") {
    getElement("#homeBtn").hidden = true;

    // forget everything the last person typed
    state.name = "";
    state.phone = "";
    state.pin = "";
    state.adminPin = "";
    state.rental = null;
    state.selectedLockerId = null;

    const inputs = getAllElements("input");
    for (let i = 0; i < inputs.length; i = i + 1) {
      inputs[i].value = "";
    }
  } else {
    getElement("#homeBtn").hidden = false;
  }

  if (screenName === "forgot") {
    state.contactedAdmin = false;
  }

  // get the newest locker list from the back end
  if (screenName === "choose-locker") {
    loadLockers("/lockers", true);
  }

  // Automatic transition after payment
  if (screenName === "payment") {
    timerTimeout = setTimeout(function() {
      submitRental();
    }, 2000);
  }

  // Automatic transition after extension payment
  if (screenName === "extend-payment") {
    timerTimeout = setTimeout(function() {
      submitExtension();
    }, 2000);
  }

  render();
}

// ---------- On-screen keyboard (for the touchscreen) ----------

let activeInput = null; // the text field that is being typed in

const LETTER_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"];
const NUMBER_ROWS = ["123", "456", "789"];

// Builds one row of key buttons (extraHtml adds special keys at the end of the row)
function buildKeyRow(keys, extraHtml) {
  let html = '<div class="krow">';
  for (let i = 0; i < keys.length; i = i + 1) {
    html = html + '<button class="btn secondary key" data-key="' + keys[i] + '">' + keys[i] + '</button>';
  }
  html = html + extraHtml + '</div>';
  return html;
}

// Builds the keyboard: numbers only for phone and PIN fields, letters for the name
function buildKeyboard(numbersOnly) {
  const backKey = '<button class="btn secondary key wide" data-key="back">⌫</button>';
  const doneKey = '<button class="btn primary key wide" data-key="done">Done</button>';
  let html = "";

  if (numbersOnly) {
    for (let i = 0; i < NUMBER_ROWS.length; i = i + 1) {
      html = html + buildKeyRow(NUMBER_ROWS[i], "");
    }
    html = html + '<div class="krow">' + backKey + '<button class="btn secondary key" data-key="0">0</button>' + doneKey + '</div>';
  } else {
    html = html + buildKeyRow(LETTER_ROWS[0], "");
    html = html + buildKeyRow(LETTER_ROWS[1], "");
    html = html + buildKeyRow(LETTER_ROWS[2], backKey);
    html = html + '<div class="krow">';
    html = html + '<button class="btn secondary key" data-key="-">-</button>';
    html = html + '<button class="btn secondary key space" data-key="space">space</button>';
    html = html + '<button class="btn secondary key" data-key="\'">\'</button>';
    html = html + doneKey + '</div>';
  }
  return html;
}

function showKeyboard(input) {
  activeInput = input;
  const numbersOnly = input.type === "tel" || input.getAttribute("inputmode") === "numeric";
  const keyboard = getElement("#keyboard");
  keyboard.innerHTML = buildKeyboard(numbersOnly);
  keyboard.hidden = false;
}

function hideKeyboard() {
  activeInput = null;
  getElement("#keyboard").hidden = true;
}

// Types (or deletes) one character in the active text field
function pressKey(key) {
  if (activeInput === null) {
    return;
  }

  if (key === "done") {
    hideKeyboard();
    return;
  }

  if (key === "back") {
    activeInput.value = activeInput.value.slice(0, -1);
    return;
  }

  if (key === "space") {
    key = " ";
  }

  // names: start each word with a capital letter
  if (activeInput.type === "text") {
    const lastChar = activeInput.value.slice(-1);
    if (activeInput.value === "" || lastChar === " " || lastChar === "-") {
      key = key.toUpperCase();
    }
  }

  // respect the maximum length of the field (the PIN fields stop at 6)
  if (activeInput.maxLength > 0 && activeInput.value.length >= activeInput.maxLength) {
    return;
  }
  activeInput.value = activeInput.value + key;
}

// also open the keyboard when a field is selected without a click (for example with the Tab key)
document.addEventListener("focusin", function(event) {
  if (event.target.tagName === "INPUT") {
    showKeyboard(event.target);
  }
});

// Global click event listener
document.addEventListener("click", async function(event) {
  // keys of the on-screen keyboard
  const keyButton = event.target.closest("[data-key]");
  if (keyButton !== null) {
    pressKey(keyButton.dataset.key);
    return;
  }

  // tapping a text field opens the keyboard
  if (event.target.tagName === "INPUT") {
    showKeyboard(event.target);
    return;
  }

  // a new button press clears the old pop-up message
  getElement("#toast").hidden = true;

  const goButton = event.target.closest("[data-go]");
  if (goButton !== null) {
    goToScreen(goButton.dataset.go);
    return;
  }

  const actionButton = event.target.closest("[data-act]");
  if (actionButton === null || actionButton.disabled) {
    return;
  }

  const action = actionButton.dataset.act;
  const lockerId = actionButton.dataset.id;
  const durationValue = actionButton.dataset.d;

  if (action === "pick") {
    state.selectedLockerId = lockerId;
  } else if (action === "dur") {
    state.duration = durationValue;
  } else if (action === "ext") {
    state.extendDuration = durationValue;
  } else if (action === "detailsnext") {
    // checks the form, then saves what the customer typed
    const name = getElement("#nameInput").value.trim();
    const phone = cleanPhone(getElement("#phoneInput").value);
    const pin = getElement("#pinInput").value;

    if (name === "" || phone === "" || pin === "") {
      showMessage("Please fill in your name, phone number and PIN.");
      return;
    }
    if (!/^[0-9]{4,6}$/.test(pin)) {
      showMessage("PIN must be 4 to 6 digits.");
      return;
    }

    state.name = name;
    state.phone = phone;
    state.pin = pin;
    goToScreen("duration");
    return;
  } else if (action === "login") {
    // customer login: the back end checks the phone + PIN and unlocks the locker
    const phone = cleanPhone(getElement("#loginPhone").value);
    const pin = getElement("#loginPin").value;

    const result = await callServer("/open-locker", "POST", { phone: phone, pin: pin });
    if (!result.ok) {
      showError(result);
      return;
    }

    state.phone = phone;
    state.pin = pin;
    state.rental = {
      id: String(result.data.locker_number),
      end: parseServerTime(result.data.end_time),
      unlocked: true
    };
    goToScreen("rental");
    return;
  } else if (action === "myunlock") {
    // customer presses Unlock on their rental screen
    const result = await callServer("/open-locker", "POST", { phone: state.phone, pin: state.pin });
    if (!result.ok) {
      showError(result);
      return;
    }
    state.rental.unlocked = true;
    state.rental.end = parseServerTime(result.data.end_time);
  } else if (action === "endhome") {
    // customer ends their rental early
    const result = await callServer("/end-rental", "POST", { phone: state.phone, pin: state.pin });
    if (!result.ok) {
      showError(result);
      return;
    }
    goToScreen("welcome");
    return;
  } else if (action === "contact") {
    // "Forgot PIN" screen
    const result = await callServer("/forgot-pin", "POST", { phone: cleanPhone(getElement("#loginPhone").value) });
    if (!result.ok) {
      showError(result);
      return;
    }
    state.forgotMessage = result.data.message;
    state.contactedAdmin = true;
  } else if (action === "adminlogin") {
    // administrator sign in: we test the PIN by asking for the locker list
    const pin = getElement("#adminPinInput").value;
    const result = await callServer("/admin/lockers?admin_pin=" + encodeURIComponent(pin), "GET");
    if (!result.ok) {
      showError(result);
      return;
    }
    state.adminPin = pin;
    setLockers(result.data);
    goToScreen("admin");
    return;
  } else if (action === "door") {
    // administrator unlocks a locker
    const result = await callServer("/admin/unlock", "POST", {
      admin_pin: state.adminPin,
      locker_number: Number(lockerId)
    });
    if (!result.ok) {
      showError(result);
      return;
    }
    await loadLockers(adminLockersPath(), true);
  } else if (action === "end") {
    // administrator force-ends a rental
    const result = await callServer("/admin/end-rental", "POST", {
      admin_pin: state.adminPin,
      locker_number: Number(lockerId)
    });
    if (!result.ok) {
      showError(result);
      return;
    }
    await loadLockers(adminLockersPath(), true);
  } else if (action === "off") {
    // administrator disables a locker, or puts a disabled one back in service
    const locker = findLocker(lockerId);
    let path = "/admin/disable";
    if (locker !== null && isLockerOff(locker)) {
      path = "/admin/enable";
    }

    const result = await callServer(path, "POST", {
      admin_pin: state.adminPin,
      locker_number: Number(lockerId)
    });
    if (!result.ok) {
      showError(result);
      return;
    }
    await loadLockers(adminLockersPath(), true);
  }

  render();
});

// Update display automatically every second for timers
let refreshCounter = 0;
setInterval(function() {
  if (
    state.screen === "choose-locker" ||
    state.screen === "success" ||
    state.screen === "rental" ||
    state.screen === "admin"
  ) {
    render();
  }

  // every 5 seconds, ask the back end for fresh locker information
  refreshCounter = refreshCounter + 1;
  if (refreshCounter % 5 === 0) {
    if (state.screen === "choose-locker") {
      loadLockers("/lockers", false);
    } else if (state.screen === "admin") {
      loadLockers(adminLockersPath(), false);
    }
  }
}, 1000);

// Initialize application
goToScreen("welcome");
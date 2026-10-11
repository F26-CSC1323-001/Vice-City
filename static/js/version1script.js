// Helper functions to select HTML elements easily
function getElement(selector) {
  return document.querySelector(selector);
}

function getAllElements(selector) {
  return Array.from(document.querySelectorAll(selector));
}

// Store available duration options [Name, Price, Minutes]
const DURATIONS = [
  ["30 minutes", "$2.00", 30],
  ["1 hour", "$3.00", 60],
  ["2 hours", "$5.00", 120],
  ["4 hours", "$8.00", 240],
  ["All day", "$12.00", 480]
];

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

// Application State Object
const state = {
  screen: "welcome",
  selectedLockerId: null,
  duration: "1 hour",
  extendDuration: "1 hour",
  contactedAdmin: false,
  now: Date.now(),
  lockers: [
    { id: "1", end: null, open: false, off: false },
    { id: "2", end: null, open: false, off: false },
    { id: "3", end: null, open: false, off: false },
    { id: "4", end: null, open: false, off: false }
  ]
};

let timerTimeout = null;

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
  if (locker.end !== null && locker.end > state.now) {
    return true;
  }
  return false;
}

// Check if a locker is available for rent
function isLockerFree(locker) {
  if (!isLockerBusy(locker) && !locker.off) {
    return true;
  }
  return false;
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

// Find active locker or fall back to selected/first
function getActiveLocker() {
  const selectedLocker = findLocker(state.selectedLockerId);
  if (selectedLocker !== null && isLockerBusy(selectedLocker)) {
    return selectedLocker;
  }

  for (let i = 0; i < state.lockers.length; i = i + 1) {
    if (isLockerBusy(state.lockers[i])) {
      return state.lockers[i];
    }
  }

  if (selectedLocker !== null) {
    return selectedLocker;
  }
  return state.lockers[0];
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

  if (locker.off) {
    label = "Disabled";
    tagClass = "danger";
  } else if (isLockerBusy(locker)) {
    label = "Occupied";
    tagClass = "warn";
  }

  let doorStatus = "Door closed";
  if (locker.open) {
    doorStatus = "Door open";
  }

  let rentalStatus = "No rental";
  if (isLockerBusy(locker)) {
    rentalStatus = getMinutesLeft(locker) + "m left";
  } else if (locker.off) {
    rentalStatus = "Offline";
  }

  let unlockBtnText = "Unlock";
  if (locker.open) {
    unlockBtnText = "Lock";
  }

  let offBtnText = "Disable";
  let offBtnClass = "warn";
  if (locker.off) {
    offBtnText = "Enable";
    offBtnClass = "secondary";
  }

  let disabledAttr = "";
  if (locker.off) {
    disabledAttr = "disabled";
  }

  let endDisabledAttr = "";
  if (!isLockerBusy(locker)) {
    endDisabledAttr = "disabled";
  }

  let html = '<div class="acard">';
  html = html + '<div class="row"><b class="body">Locker ' + locker.id + '</b><span class="tag ' + tagClass + '">' + label + '</span></div>';
  html = html + '<div class="stat"><div>' + doorStatus + '</div><div>' + rentalStatus + '</div></div>';
  html = html + '<div class="acts">';
  html = html + '<button class="btn secondary sm" data-act="door" data-id="' + locker.id + '" ' + disabledAttr + '>' + unlockBtnText + '</button>';
  html = html + '<button class="btn danger sm" data-act="end" data-id="' + locker.id + '" ' + endDisabledAttr + '>End</button>';
  html = html + '<button class="btn ' + offBtnClass + ' sm" data-act="off" data-id="' + locker.id + '">' + offBtnText + '</button>';
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
      if (isLockerBusy(state.lockers[i])) {
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
    let lockerName = "3";
    if (state.selectedLockerId !== null) {
      lockerName = state.selectedLockerId;
    }
    setText("#sTitle", "Locker " + lockerName + " is open");

    let endTime = state.now + getMinutes(state.duration) * 60000;
    if (selectedLocker !== null && selectedLocker.end !== null) {
      endTime = selectedLocker.end;
    }
    setText("#sEnd", formatTime(endTime));
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
    if (locker.open) {
      statusText = "Door unlocked";
    }

    let buttonActionText = "Unlock";
    if (locker.open) {
      buttonActionText = "Lock";
    }

    setText("#rTitle", "Locker " + locker.id);
    setText("#rBadge", statusText);
    setText("#rTime", timeText);

    let endTimestamp = state.now;
    if (locker.end !== null) {
      endTimestamp = locker.end;
    }
    setText("#rEnd", formatTime(endTimestamp));
    setText("#doorBtn", buttonActionText);

    getElement("#doorBtn").dataset.id = locker.id;
    getElement("#endBtn").dataset.id = locker.id;
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
      setText("#forgotText", "The administrator has been notified. Please wait for assistance.");
      setText("#contactBtn", "Administrator Contacted");
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

// Function to handle switching screens
function goToScreen(screenName) {
  clearTimeout(timerTimeout);
  state.screen = screenName;

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
  } else {
    getElement("#homeBtn").hidden = false;
  }

  if (screenName === "forgot") {
    state.contactedAdmin = false;
  }

  // Automatic transition after payment
  if (screenName === "payment") {
    timerTimeout = setTimeout(function() {
      const locker = findLocker(state.selectedLockerId);
      if (locker !== null) {
        locker.end = Date.now() + getMinutes(state.duration) * 60000;
        locker.open = true;
      }
      goToScreen("success");
    }, 2000);
  }

  // Automatic transition after extension payment
  if (screenName === "extend-payment") {
    timerTimeout = setTimeout(function() {
      const locker = getActiveLocker();
      let startTime = Date.now();
      if (locker.end !== null && locker.end > Date.now()) {
        startTime = locker.end;
      }
      locker.end = startTime + getMinutes(state.extendDuration) * 60000;
      goToScreen("rental");
    }, 2000);
  }

  render();
}

// Global click event listener
document.addEventListener("click", function(event) {
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
  const locker = findLocker(lockerId);

  if (action === "pick") {
    state.selectedLockerId = lockerId;
  } else if (action === "dur") {
    state.duration = durationValue;
  } else if (action === "ext") {
    state.extendDuration = durationValue;
  } else if (action === "door") {
    if (locker !== null) {
      locker.open = !locker.open;
    }
  } else if (action === "end") {
    if (locker !== null) {
      locker.end = null;
      locker.open = false;
    }
  } else if (action === "off") {
    if (locker !== null) {
      locker.off = !locker.off;
    }
  } else if (action === "contact") {
    state.contactedAdmin = true;
  } else if (action === "endhome") {
    if (locker !== null) {
      locker.end = null;
      locker.open = false;
    }
    state.selectedLockerId = null;
    goToScreen("welcome");
    return;
  }

  render();
});

// Update display automatically every second for timers
setInterval(function() {
  if (
    state.screen === "choose-locker" ||
    state.screen === "success" ||
    state.screen === "rental" ||
    state.screen === "admin"
  ) {
    render();
  }
}, 1000);

// Initialize application
goToScreen("welcome");
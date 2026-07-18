let expenses = [];

function addExpense() {
  const desc = document.getElementById('desc').value.trim();
  const amount = parseFloat(document.getElementById('amount').value);
  if (!desc || isNaN(amount)) {
    return; // ignore empty/invalid input
  }
  expenses.push({ desc, amount });
  render();
  // Clear the form for the next entry
  document.getElementById('expense-form').reset();
  document.getElementById('desc').focus();
}

function render() {
  const list = document.getElementById('expense-list');
  list.innerHTML = '';
  let total = 0;
  for (const e of expenses) {
    const li = document.createElement('li');
    li.textContent = e.desc + ' — $' + e.amount;
    list.appendChild(li);
    total += e.amount;
  }
  document.getElementById('total').textContent = total;
}

function setup() {
  // Single handler: the form's submit event covers both clicking the
  // submit button and pressing Enter, so no separate click listener is
  // needed (having both was one source of duplicate entries).
  document.getElementById('expense-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    addExpense();
  });
}

// The script is loaded at the end of <body>, so the DOM is already
// available — call setup() exactly once. (Previously setup() ran both
// immediately AND on DOMContentLoaded, attaching every listener twice,
// which was the other source of duplicate entries.)
setup();

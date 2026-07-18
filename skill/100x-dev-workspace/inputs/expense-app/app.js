let expenses = [];

function addExpense() {
  const desc = document.getElementById('desc').value;
  const amount = parseFloat(document.getElementById('amount').value);
  expenses.push({ desc, amount });
  render();
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
  document.getElementById('expense-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    addExpense();
  });
  document.getElementById('add-btn').addEventListener('click', function () {
    addExpense();
  });
}

document.addEventListener('DOMContentLoaded', setup);
setup();

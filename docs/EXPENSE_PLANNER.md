# Expense Planner

**Menu:** Orders → Expense Planner  
**URL:** `/tasks/upcoming-expenses/`  
**Access:** active superusers only. Staff permissions alone do not grant access.

This is a standalone USD payment tracker. It does not post accounting expenses,
change client/supplier balances, or create invoice payments.

## Using the planner

1. Add payment types using **Manage payment types**. Rent, Utilities, Salaries,
   Subscriptions, and Other are included initially.
2. Choose **Add payment** and enter a type, free-text description, amount, first
   due date, and One time or Monthly frequency.
3. The default list shows every unpaid payment, including overdue payments.
   Mark a row paid to remove it from this list and deduct it from the balance.
4. Choose Paid or All payments to review history or restore a payment to unpaid.
   Paid date and user are retained while a payment is marked paid.
5. Filter by payment type, dates, frequency, search text, status, or overdue-only.
   Totals use all matching records, not only the current table page (50 rows).
6. Edit unpaid installments using the row's Edit link. Mark a paid payment
   unpaid before correcting it. Installment edits do not change the monthly plan.
7. Use **Monthly commitments → Stop recurrence** to stop future installments.
   Payments already created remain in the list and history. To replace a monthly
   amount or description, stop the old plan and add the replacement.

## Monthly behavior

- The first installment is created immediately, even if its date is in the future.
- Other installments accrue through the current calendar month as the page is
  opened. No extra scheduled task or deployment configuration is needed.
- Catch-up generation includes missed months after a period of inactivity.
- Every month has a separate amount and paid status. Unpaid months accumulate.
  Paying November does not settle October or create December early.
- A plan starting on 31 January uses 28/29 February, then returns to 31 March.
- Editing an installment's actual due date does not create a second installment
  for that month. Generation is protected by a database uniqueness constraint.
- Future date filters do not generate hypothetical future installments.

## Deploy

Migration `expenses.0003_upcoming_expense_planner` adds three new tables and the
initial payment types. It does not modify existing invoices or expenses.

```bash
cd /home/ghaithtravel/ghaithleads && BACKUP_MEDIA=no bash deploy/deploy.sh
```

Sophia synchronization remains paused.

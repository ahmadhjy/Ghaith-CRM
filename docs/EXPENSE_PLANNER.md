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
6. **Record payment** accepts partial amounts: an original USD 1,000 payment
   with USD 700 paid keeps its original amount and shows USD 300 remaining.
   Multiple receipts are retained in Payment history. Settle remaining pays the
   rest; Undo payments reverses recorded receipts and restores the full balance.
7. **Edit this installment** changes one row. **Edit entire schedule** changes
   the original start date, amount, description, and frequency, including unpaid
   installments and future months. Moving the start from November to October
   creates October's missing installment. Paid and partially paid rows are never
   rewritten by schedule changes.
8. **Delete installment** removes one unpaid row without regenerating it.
   **Edit entire schedule → Delete entire expense** removes the schedule and
   its unpaid rows. Deletion is soft (retained internally). Expenses with recorded
   payments are protected; reverse the receipts before deleting, or stop recurrence.
9. Use **Monthly commitments → Stop recurrence** to stop future installments.
   Payments already created remain in the list and history.

## Monthly behavior

- Set **Last due date** to end a fixed-term schedule automatically (inclusive).
  Five installments starting 1 November end on 1 March. Existing paid and unpaid
  records are kept. Alternatively use **Monthly commitments → Stop recurrence**
  to stop manually without deleting history.
- **Stop recurrence** is available directly on each active monthly row and in
  the expanded **Monthly commitments** section at the bottom of the page.
- The checkbox is labeled **Paid**: unchecked means unpaid; checking it pays the
  entire remaining balance. Use **Record payment** for partial amounts.

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

Migration `expenses.0003_upcoming_expense_planner` adds the planner.
`expenses.0004_expense_partial_payments_and_schedule_edits` adds receipts, partial
balances, and deletion flags. Existing fully paid installments are backfilled
with their full paid amount. Existing invoices and accounting expenses are unchanged.

```bash
cd /home/ghaithtravel/ghaithleads && BACKUP_MEDIA=no bash deploy/deploy.sh
```

Sophia synchronization remains paused.

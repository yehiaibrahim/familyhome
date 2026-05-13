# This file was created using claude and chatgpt.


# Checking the payments transferred to the business by the delivery company against the customers' payments, Automating a repetitive accounting process.

#!/usr/bin/env python3
"""
Qimmah Payment Reconciliation Tool
Verifies that payment totals match the sum of individual shipment entries
"""

import requests
import json
import getpass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import warnings
from decimal import Decimal

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

BASE_URL = "https://qimmah.lg.accuratess.com:8443/graphql"

class QimmahPaymentReconciler:
    def __init__(self):
        self.token = None
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        self.results = []

    def login(self, username: str, password: str) -> bool:
        """Authenticate and get JWT token"""
        print(f"[*] Logging in as {username}...")

        query = """
        mutation Login($input: LoginInput!) {
          login(input: $input) {
            token
            user {
              id
              username
            }
          }
        }
        """

        payload = {
            "query": query,
            "variables": {
                "input": {
                    "username": username,
                    "password": password
                }
            }
        }

        try:
            response = requests.post(
                BASE_URL,
                json=payload,
                headers=self.headers,
                verify=False,
                timeout=10
            )

            data = response.json()

            if 'errors' in data:
                print(f"[!] Login error: {data['errors']}")
                return False

            if 'data' in data and data['data'].get('login'):
                login_data = data['data']['login']
                self.token = login_data.get('token')

                if self.token:
                    print(f"[+] Login successful!")
                    self.headers['Authorization'] = f'Bearer {self.token}'
                    return True

            return False

        except requests.exceptions.RequestException as e:
            print(f"[!] Login error: {e}")
            return False

    def fetch_payments_list(self, from_date: str, to_date: str, payment_type: str = "CUSTM",
                           page: int = 1, per_page: int = 50) -> List[Dict]:
        """Fetch list of payments for a date range"""
        query = """
        query GetPayments($type: String!, $fromDate: String!, $toDate: String!, $page: Int!, $perPage: Int!) {
          payments(type: $type, fromDate: $fromDate, toDate: $toDate, page: $page, perPage: $perPage) {
            paginatorInfo {
              total
              currentPage
              lastPage
              perPage
            }
            data {
              id
              code
              date
              customer {
                name
                code
              }
              sumEntries {
                paymentAmount
                deliveredAmount
                piecesCount
              }
            }
          }
        }
        """

        payload = {
            "query": query,
            "variables": {
                "type": payment_type,
                "fromDate": from_date,
                "toDate": to_date,
                "page": page,
                "perPage": per_page
            }
        }

        try:
            response = requests.post(
                BASE_URL,
                json=payload,
                headers=self.headers,
                verify=False,
                timeout=10
            )

            data = response.json()

            if 'errors' in data:
                print(f"[!] Error fetching payments: {data['errors']}")
                return []

            if 'data' in data and data['data'].get('payments'):
                payments_data = data['data']['payments']
                return payments_data.get('data', [])

            return []

        except requests.exceptions.RequestException as e:
            print(f"[!] Request error: {e}")
            return []

    def fetch_payment_detail(self, payment_id: int) -> Optional[Dict]:
        """Fetch complete payment details including sumEntries"""
        query = """
        query GetPayment($id: Int!) {
          payment(id: $id) {
            id
            code
            date
            customer {
              id
              name
              code
            }
            type {
              code
            }
            sumEntries {
              deliveredAmount
              piecesCount
              collectedFees
              dueFees
              weight
              paymentAmount
            }
            transactionType {
              name
            }
            createdBy {
              username
            }
          }
        }
        """

        payload = {
            "query": query,
            "variables": {"id": int(payment_id)}
        }

        try:
            response = requests.post(
                BASE_URL,
                json=payload,
                headers=self.headers,
                verify=False,
                timeout=10
            )

            data = response.json()

            if 'errors' in data:
                print(f"[!] Error fetching payment {payment_id}: {data['errors']}")
                return None

            if 'data' in data and data['data'].get('payment'):
                return data['data']['payment']

            return None

        except requests.exceptions.RequestException as e:
            print(f"[!] Request error: {e}")
            return None

    def fetch_payment_entries(self, payment_id: int, page: int = 1) -> List[Dict]:
        """Fetch all entries (shipments) for a payment"""
        query = """
        query GetPaymentEntries($paymentId: Int!, $page: Int!) {
          payment(id: $paymentId) {
            entries(page: $page) {
              paginatorInfo {
                total
                currentPage
                lastPage
              }
              data {
                paidAmount
                shipment {
                  code
                  deliveredAmount
                  collectedFees
                  returningDueFees
                  recipientName
                }
              }
            }
          }
        }
        """

        payload = {
            "query": query,
            "variables": {
                "paymentId": int(payment_id),
                "page": page
            }
        }

        try:
            response = requests.post(
                BASE_URL,
                json=payload,
                headers=self.headers,
                verify=False,
                timeout=10
            )

            data = response.json()

            if 'errors' in data:
                print(f"[!] Error fetching entries: {data['errors']}")
                return []

            if 'data' in data and data['data'].get('payment'):
                payment_data = data['data']['payment']
                entries_data = payment_data.get('entries', {})
                return entries_data.get('data', [])

            return []

        except requests.exceptions.RequestException as e:
            print(f"[!] Request error: {e}")
            return []

    def reconcile_payment(self, payment_id: int) -> Dict:
        """Fetch payment and entries, then reconcile"""
        print(f"\n[*] Reconciling payment {payment_id}...")

        # Fetch payment details
        payment = self.fetch_payment_detail(payment_id)
        if not payment:
            print(f"[!] Could not fetch payment {payment_id}")
            return None

        # Fetch all entries for this payment
        entries = self.fetch_payment_entries(payment_id)

        # Calculate sum of paid amounts
        entries_sum = Decimal('0')
        entry_details = []

        for entry in entries:
            paid_amount = Decimal(str(entry.get('paidAmount', 0)))
            entries_sum += paid_amount

            shipment = entry.get('shipment', {})
            entry_details.append({
                'paidAmount': float(paid_amount),
                'shipmentCode': shipment.get('code'),
                'recipientName': shipment.get('recipientName')
            })

        # Get payment amount from sumEntries
        payment_amount = Decimal(str(payment.get('sumEntries', {}).get('paymentAmount', 0)))

        # Check if they match
        matches = entries_sum == payment_amount
        discrepancy = float(payment_amount - entries_sum)

        result = {
            'paymentId': payment_id,
            'paymentCode': payment.get('code'),
            'date': payment.get('date'),
            'customer': payment.get('customer', {}).get('name'),
            'customerCode': payment.get('customer', {}).get('code'),
            'paymentAmount': float(payment_amount),
            'entriesSum': float(entries_sum),
            'entriesCount': len(entries),
            'matches': matches,
            'discrepancy': discrepancy,
            'entries': entry_details
        }

        # Print result
        status = "✓ MATCH" if matches else "✗ MISMATCH"
        print(f"[+] {status}")
        print(f"    Payment Amount: {float(payment_amount):,.2f}")
        print(f"    Entries Sum:    {float(entries_sum):,.2f}")
        if not matches:
            print(f"    Discrepancy:    {discrepancy:+,.2f}")

        return result

    def save_results(self, filename: Optional[str] = None):
        """Save reconciliation results to JSON"""
        if filename is None:
            filename = f"qimmah_reconciliation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        print(f"\n[+] Results saved to {filename}")
        return filename

    def print_summary(self):
        """Print summary of all reconciliations"""
        if not self.results:
            print("[!] No results to summarize")
            return

        print("\n" + "="*70)
        print("RECONCILIATION SUMMARY")
        print("="*70)

        total_payments = len(self.results)
        matched = sum(1 for r in self.results if r.get('matches'))
        mismatched = total_payments - matched

        print(f"Total Payments Checked: {total_payments}")
        print(f"Matched:                {matched}")
        print(f"MISMATCHES:             {mismatched}")

        if mismatched > 0:
            print("\n⚠️  MISMATCHED PAYMENTS:")
            for r in self.results:
                if not r.get('matches'):
                    print(f"\n  Payment ID: {r.get('paymentId')}")
                    print(f"  Code: {r.get('paymentCode')}")
                    print(f"  Customer: {r.get('customer')}")
                    print(f"  Date: {r.get('date')}")
                    print(f"  Payment Amount: {r.get('paymentAmount'):,.2f}")
                    print(f"  Entries Sum:    {r.get('entriesSum'):,.2f}")
                    print(f"  Discrepancy:    {r.get('discrepancy'):+,.2f}")

def main():
    reconciler = QimmahPaymentReconciler()

    print("="*70)
    print("QIMMAH PAYMENT RECONCILIATION TOOL")
    print("="*70 + "\n")

    # Login
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    if not reconciler.login(username, password):
        print("[!] Login failed. Exiting.")
        return

    # Choose action
    print("\nOptions:")
    print("1. Reconcile a specific payment ID")
    print("2. Reconcile all payments in a date range")

    choice = input("\nSelect option (1 or 2): ").strip()

    if choice == '1':
        # Single payment
        payment_id = input("Enter payment ID: ").strip()
        if payment_id.isdigit():
            result = reconciler.reconcile_payment(int(payment_id))
            if result:
                reconciler.results.append(result)
        else:
            print("[!] Invalid payment ID")

    elif choice == '2':
        # Date range
        print("\nEnter date range (YYYY-MM-DD format):")
        from_date = input("From date (e.g., 2026-05-01): ").strip()
        to_date = input("To date (e.g., 2026-05-13): ").strip()

        # Validate dates
        try:
            datetime.strptime(from_date, '%Y-%m-%d')
            datetime.strptime(to_date, '%Y-%m-%d')
        except ValueError:
            print("[!] Invalid date format")
            return

        # Fetch payments list
        print(f"\n[*] Fetching payments from {from_date} to {to_date}...")
        payments_list = reconciler.fetch_payments_list(from_date, to_date)

        if payments_list:
            print(f"[+] Found {len(payments_list)} payments")

            # Reconcile each payment
            for i, payment_summary in enumerate(payments_list, 1):
                payment_id = payment_summary.get('id')
                print(f"\n[{i}/{len(payments_list)}] Processing payment {payment_id}...")

                result = reconciler.reconcile_payment(payment_id)
                if result:
                    reconciler.results.append(result)
        else:
            print("[!] No payments found for this date range")

    # Save and display summary
    if reconciler.results:
        reconciler.save_results()
        reconciler.print_summary()
    else:
        print("\n[!] No results to save")

    print("\n[+] Done!")

if __name__ == "__main__":
    main()
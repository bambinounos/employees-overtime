import os
import sys
import django
from pathlib import Path

# Add project root to path
FILE = Path(__file__).resolve()
ROOT = FILE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salary_management.settings")
django.setup()

from playwright.sync_api import sync_playwright, expect
from django.contrib.auth.models import User
from employees.models import Employee
from datetime import date
from django.utils import timezone

def setup_test_data():
    """Create a superuser and test employees."""
    if not User.objects.filter(username='testadmin').exists():
        user = User(
            username='testadmin',
            email='admin@example.com',
            is_staff=True,
            is_superuser=True,
            last_login=timezone.now()
        )
        user.set_password('testpassword')
        user.save()

    Employee.objects.all().delete() # Clean up previous test data

    Employee.objects.create(
        name='Active Employee',
        email='active@example.com',
        hire_date=date(2023, 1, 1)
    )
    Employee.objects.create(
        name='Inactive Employee',
        email='inactive@example.com',
        hire_date=date(2023, 1, 1),
        end_date=date(2024, 1, 1)
    )

def run_verification(playwright):
    """
    This script verifies the employee deactivation feature.
    """
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # 1. Login
        page.goto("http://127.0.0.1:8000/login/")
        page.fill("input[name='username']", "testadmin")
        page.fill("input[name='password']", "testpassword")
        page.click("button[type='submit']")
        expect(page).to_have_url("http://127.0.0.1:8000/")

        # 2. Go to employee list and verify default view
        page.goto("http://127.0.0.1:8000/employees/")
        expect(page.get_by_role("cell", name="Active Employee", exact=True)).to_be_visible()
        expect(page.get_by_role("cell", name="Inactive Employee", exact=True)).not_to_be_visible()

        # 3. Show inactive employees and verify
        page.get_by_role("link", name="Show Inactive").click()
        expect(page.get_by_role("cell", name="Active Employee", exact=True)).to_be_visible()
        expect(page.get_by_role("cell", name="Inactive Employee", exact=True)).to_be_visible()
        page.screenshot(path="jules-scratch/verification/verification_show_inactive.png")

        # 4. Terminate the active employee
        terminate_button = page.locator(
            "//tr[td[contains(text(), 'Active Employee')]]//button[contains(text(), 'Terminate')]"
        )

        # Handle the confirmation dialog
        page.on("dialog", lambda dialog: dialog.accept())

        terminate_button.click()

        # 5. Verify the employee is now inactive
        expect(page.get_by_text("The contract for Active Employee has been terminated.")).to_be_visible()
        expect(page.get_by_role("cell", name="Active Employee", exact=True)).not_to_be_visible()
        page.screenshot(path="jules-scratch/verification/verification_terminated.png")

    finally:
        browser.close()

if __name__ == "__main__":
    setup_test_data()
    with sync_playwright() as playwright:
        run_verification(playwright)
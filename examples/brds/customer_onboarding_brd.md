# Business Requirements Document — Digital Customer Onboarding

**Business owner:** Head of Retail Operations
**Version:** 0.9 (draft)

## 1. Background
New retail customers currently open accounts by visiting a branch and filling in paper forms.
Onboarding takes 5–7 working days, around 30% of applications are abandoned, and back-office
staff re-key every form into the core banking system.

## 2. Objectives
- Let customers open an account fully online in under 15 minutes.
- Reduce abandonment to below 10%.
- Remove manual re-keying of application data.
- Stay compliant with KYC and AML regulations.

## 3. Scope
In scope: savings and current accounts for individual customers, web and mobile web.
Out of scope: business accounts, joint accounts (phase 2), credit products.

## 4. Business requirements
1. Customers can start an application on the website and save and resume it later.
2. Customers verify identity by uploading a government ID and taking a selfie.
3. The system checks the customer against sanctions and PEP lists.
4. Applications that pass all checks are approved automatically; others go to a review queue.
5. Operations staff can review flagged applications, request more documents, approve or reject.
6. Approved customers get an account number and welcome email immediately.
7. Account details are created in the core banking system automatically.
8. Management wants a dashboard of application volumes, conversion and processing time.

## 5. Non-functional expectations
- Should be available most of the time and handle marketing campaign peaks.
- Customer data must be secure and kept for the legally required period.
- Must work on mobile phones.

## 6. Constraints
- Core banking system exposes a SOAP API only.
- Go-live required before the next financial year.
- Budget has not been confirmed.

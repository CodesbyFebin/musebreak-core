# Run a verifiable synthetic invoice

Use Python 3.12 for the closest match to the recorded qualification. The exercise calls no live model or external business provider, and uses no physical MetaKey.

```sh
git clone https://github.com/CodesbyFebin/musebreak-core.git
cd musebreak-core
git fetch origin feat/verified-invoice-receipts
git switch --track origin/feat/verified-invoice-receipts
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
python scripts/verified_invoice_demo.py --out /tmp/my-new-musebreak-demo
python verification/invoice_receipt.py \
  --receipt /tmp/my-new-musebreak-demo/receipt.json \
  --public-key /tmp/my-new-musebreak-demo/signing-public.pem \
  --database /tmp/my-new-musebreak-demo/business-snapshot.sqlite
```

Choose a new output directory on every run. Until PR #1 is merged, the explicit branch step is required. If you already have a local branch, switch to it instead of trying to create a tracking branch twice.

## Expected evidence

Two synthetic coffee items cost 19,999 paise each. Configured per-line half-up 18 percent tax gives a total of 47,198 paise. The script rejects an unapproved issue, approves the payload, issues, and confirms duplicate issue returns the same receipt. It exports a public key, synthetic snapshot, receipt and separate-process verdict. It does not export its temporary signing private key.

## What to inspect

Read the verdict and exit status. Inspect the receipt's invoice and decision bindings, then the [workflow contract](../verification/INVOICE-WORKFLOW.md). The demo's local key is a controlled fixture, not independently distributed production trust. For a real verification process obtain the public key through a separate trusted channel and the snapshot independently.

For combined tests install `python -m pip install -e cli`, then use the command in the [qualification report](../verification/QUALIFICATION.md). Return to [wiki home](Home.md).

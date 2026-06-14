# Publishing Checklist

This repository is designed to contain only the reusable Skill framework and explicitly fictional
examples.

Before publishing:

1. Keep all real people, organizations, interviews, relationship notes, and sync state outside this
   repository.
2. Run `python3 scripts/privacy_scan.py .`.
3. Run `python3 -m unittest discover -s tests -v`.
4. Review the complete staged file list and diff.
5. Confirm that every example person and organization is explicitly marked as fictional.

The privacy scanner is a release guard, not a substitute for human review.

# Development

Use a virtual environment and install `requirements.txt`. Run `python -m pytest -q` from the repository root. CI uses Python 3.12 and 3.13. Tests create temporary databases/files where they mutate data; committed datasets are explicit regression fixtures.

Keep changes small and include a failing example before fixing a bug. Verify documented commands from a clean checkout. Do not describe browser mockups as deployed Python services. The root README is the maintained setup reference; nested guides retain additional context and may describe the original exercise.

## November 2026 review

Pagination now copies only validated application filters. An `endpoint` query parameter previously collided with Flask URL generation and raised TypeError. The regression exercises a page with a Previous link and checks that filters survive.

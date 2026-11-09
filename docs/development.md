# Development

Use a virtual environment and install `requirements.txt`. Run `python -m pytest -q` from the repository root. CI uses Python 3.12 and 3.13. Tests create temporary databases/files where they mutate data; committed datasets are explicit regression fixtures.

Keep changes small and include a failing example before fixing a bug. Verify documented commands from a clean checkout. Do not describe browser mockups as deployed Python services. The root README is the maintained setup reference; nested guides retain additional context and may describe the original exercise.

This portfolio received an automated engineering review. The repository owner should reproduce the setup, read the changes and explain the tests before claiming personal implementation experience.

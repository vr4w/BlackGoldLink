# Contributing

Feedback in English or German is welcome in Issues. Include the steps, expected behavior, browser and approximate time. Use the idea template for usability feedback.

For code changes, open a small pull request against `main`. Preserve current routes, data fields, collection matching and the separate web/worker structure. Run `python -m unittest discover -s tests -v` and check affected pages in a browser using fictional data.

Public code and feedback do not provide access to the private test platform. Never include secrets, invite links, real collection exports or private conversations. Report security problems using GitHub's private vulnerability reporting, not public Issues.

Changes and feedback do not deploy themselves. Maintainers explicitly approve a tested `main` commit in Actions before the server updater can install it.

No open-source license has been selected yet. Public visibility does not grant an additional reuse license for the code or brand assets.

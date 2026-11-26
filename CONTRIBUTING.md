# Contributing to rocket-massprops

Thanks for taking the time! Bug reports, ideas and pull requests are all welcome.

## Report a bug or suggest a feature
Open an [issue](https://github.com/sushkoivan/rocket-massprops/issues/new/choose). For bugs, include the input (script or JSON case),
what you expected and what you got. Issues labelled
[`good first issue`](https://github.com/sushkoivan/rocket-massprops/labels/good%20first%20issue) are a good place to start.

## Set up for development
```bash
git clone https://github.com/sushkoivan/rocket-massprops
cd rocket-massprops
pip install -e ".[dev]"
pytest
```

## Pull requests
1. Fork, create a branch, make your change.
2. Add or update a test in `tests/` for every behaviour change. Engineering results should be checked against
   an independent reference (closed-form case, textbook value, published data) and the source named in the test.
3. Keep the runtime free of third-party dependencies unless there is a strong reason.
4. Run `pytest` and make sure CI is green.
5. Describe *what* and *why* in the PR. Small PRs are reviewed fastest.

## Style
- SI units internally; convert only at the edges (CLI, reports).
- Public functions get a docstring that states units.
- Readable over clever: this code is meant to be checked by engineers, not only run.

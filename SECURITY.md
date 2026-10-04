# Security Policy

## Contact

Report vulnerabilities privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability** ([direct link](https://github.com/TMHSDigital/autoclicker/security/advisories/new)). This keeps the report, the discussion and any fix in one private advisory.

If you can't use GitHub, email **info@tmhsdigital.com** (same contact as the [Code of Conduct](CODE_OF_CONDUCT.md)).

Please do not open public GitHub issues for undisclosed vulnerabilities.

## Supported versions

Security fixes are applied to the latest release on the default branch. Older tagged releases may not receive patches.

## Disclosure process

Reports arrive as private GitHub security advisories (or email). There is no bug bounty. Maintainers will acknowledge reports and work with reporters on a reasonable timeline.

## Safe contributions

This is a public repository. Do not commit:

- API keys, tokens, or passwords
- Private configuration or customer data
- Signed executables or binaries except through the release pipeline

If sensitive data is committed accidentally, contact the maintainers immediately so the history can be addressed.

This is an input-automation tool. Reports of unsafe defaults, privilege issues, or supply-chain problems in the release pipeline are in scope; “how do I abuse this against a third party” is not.

## Automated checks

Every push and pull request runs `pip-audit` against the locked dependencies and CodeQL (Python and the GitHub Actions workflows); CodeQL also runs weekly. Dependabot tracks dependency and action updates, and actions are pinned to commit SHAs.

# Security policy

Please report vulnerabilities privately through [GitHub's private vulnerability reporting](https://github.com/gpdl49/ha-daikin-india/security/advisories/new), not in a public issue.

Only the latest release is supported. You should get a reply within a week.

The client ID, client secret and RSA public key in `custom_components/daikin_india/dsiot/const.py` and `cloud_auth.py` ship inside the public Daikin AC Android app. They identify the app, not a user, so they are not a vulnerability.

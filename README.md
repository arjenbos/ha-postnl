# PostNL Home Assistant Integration
A custom integration for PostNL. 

## Install integration
- Download the browser extension and install it.
  - You can find the extension here: https://github.com/arjenbos/ha-postnl-browser-extensions
- Add the repository to HACS.
- Install the integration via HACS.
- Add the integration:
  - Name: whatever you like
  - Client ID: whatever you like (will be ignored).
  - Client secret: whatever you like (will be ignored).
  - You will be redirected to PostNL:
    - If you aren't logged in, then PostNL will show you a login page.
    - If you're already logged in, then it will redirect you back to Home Assistant oAuth2 callback (check your Home Assistant URL!).
- Done! You only need to install the lovelace.

## Install lovelace
- Go to https://github.com/peternijssen/lovelace-postnl-card. The repository is archived, however you can still use the lovelace.

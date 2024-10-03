from homeassistant.const import Platform

DOMAIN = "postnl"
VERSION = "1.4.0"
POSTNL_CLIENT_ID = "deb0a372-6d72-4e09-83fe-997beacbd137"
POSTNL_AUTH_URL = "https://login.postnl.nl/101112a0-4a0f-4bbb-8176-2f1b2d370d7c/login/authorize"
POSTNL_TOKEN_URL = "https://login.postnl.nl/101112a0-4a0f-4bbb-8176-2f1b2d370d7c/login/token"
POSTNL_REDIRECT_URI = "postnl://login"
POSTNL_SCOPE = "profile openid email address phone poa-profiles-api"

PLATFORMS = [
    Platform.SENSOR
]

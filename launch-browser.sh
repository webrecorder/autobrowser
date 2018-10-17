#!/usr/bin/env bash

google-chrome-unstable --remote-debugging-port=9222 --disable-background-networking \
    --disable-background-timer-throttling \
    --disable-client-side-phishing-detection \
    --disable-default-apps \
    --disable-extensions \
    --disable-hang-monitor \
    --disable-prompt-on-repost \
    --disable-sync \
    --disable-translate \
    --disable-domain-reliability \
    --disable-renderer-backgrounding \
    --disable-infobars \
    --disable-translate \
    --disable-features=site-per-process \
    --disable-breakpad \
    --metrics-recording-only \
    --no-first-run \
    --safebrowsing-disable-auto-update \
    --password-store=basic \
    --use-mock-keychain \
    --mute-audio \
    --autoplay-policy=no-user-gesture-required \
    about:blank


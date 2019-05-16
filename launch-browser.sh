#!/usr/bin/env bash

google-chrome-unstable --remote-debugging-port=9222\
    --disable-gpu-process-crash-limit\
    --disable-background-networking\
    --disable-background-timer-throttling\
    --disable-renderer-backgrounding\
    --disable-backgrounding-occluded-windows\
    --disable-ipc-flooding-protection\
    --disable-client-side-phishing-detection\
    --disable-popup-blocking\
    --disable-hang-monitor\
    --disable-prompt-on-repost\
    --disable-domain-reliability\
    --disable-infobars\
    --disable-features=site-per-process,TranslateUI,LazyFrameLoading,BlinkGenPropertyTrees\
    --disable-breakpad\
    --disable-backing-store-limit\
    --enable-features=NetworkService,NetworkServiceInProcess,brotli-encoding,AwaitOptimization\
    --metrics-recording-only\
    --no-first-run\
    --safebrowsing-disable-auto-update\
    --mute-audio\
#    --enable-native-gpu-memory-buffers\
#    --enable-gpu-rasterization\
    --autoplay-policy=no-user-gesture-required\
    about:blank


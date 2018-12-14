#!/bin/bash
docker build --target=behaviors --no-cache .
docker-compose build

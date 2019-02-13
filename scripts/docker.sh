#!/usr/bin/env bash
workdir="$PWD"

buildBehaviorsAPIImage () {
  echo "Building Behaviors image"
  docker build -f "${workdir}/dockerfiles/Dockerfile.behaviors" -t webrecorder/behaviors-api:latest .
  echo "Built Behaviors image"
}

buildBehaviors () {
  echo "Building behaviors"
  docker build -f "${workdir}/dockerfiles/Dockerfile.behaviors" --target behaviors -t webrecorder/behaviors-api:latest .
  echo "Built behaviors"
}

buildDriver () {
  echo "Building the driver part of the python portion"
  docker build -f "${workdir}/dockerfiles/Dockerfile.driver" -t webrecorder/autobrowser:latest .
  echo "Building the driver part of the python portion"
}

case "$1" in
    "behaviorAPI"*)
     buildBehaviorsAPIImage
    ;;

    "behaviors"*)
     buildBehaviors
    ;;

    "driver"*)
    buildDriver
    ;;

    *)
    buildBehaviorsAPIImage
    buildDriver
    ;;
esac

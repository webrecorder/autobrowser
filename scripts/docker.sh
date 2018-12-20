#!/usr/bin/env bash
workdir="$PWD"

buildBehaviorsImage () {
  echo "Building Behaviors image"
  docker build -f "${workdir}/wr-behaviors/Dockerfile.mountable" -t wrbehaviors:latest "${workdir}/wr-behaviors"
  echo "Built Behaviors image"
}

buildBehaviors () {
  echo "Building behaviors"
  docker run --rm -v "${workdir}/autobrowser/behaviors/behaviorjs:/dist" -v "${workdir}/wr-behaviors/src:/src" -i -t wrbehaviors:latest
  echo "Built behaviors"
}

buildBehaviorPython () {
  echo "Building docker image for python portion"
  docker build . --no-cache -t webrecorder/autobrowser:latest
  echo "Built docker image for python portion"
}

buildDriver () {
  echo "Building the driver part of the python portion"
  docker build . --target driver -t webrecorder/autobrowser:latest
  echo "Building the driver part of the python portion"
}

case "$1" in
    "behaviorImage"*)
     buildBehaviorsImage
    ;;

    "behaviors"*)
     buildBehaviors
    ;;

    "py"*)
     buildBehaviorPython
    ;;

    "driver"*)
    buildDriver
    ;;

    *)
    buildBehaviorsImage
    buildBehaviors
    buildBehaviorPython
    ;;
esac

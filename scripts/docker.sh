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
  docker build . -t webrecorder/autobrowser:latest
  echo "Built docker image for python portion"
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

    *)
    buildBehaviorsImage
    buildBehaviors
    buildBehaviorPython
    ;;
esac

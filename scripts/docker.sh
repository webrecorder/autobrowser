#!/usr/bin/env bash
workdir="$PWD"

buildBehaviorsImage () {
  echo "Building Behaviors image"
  docker build "${workdir}/wr-behaviors/Dockerfile" -t wrbehaviors:latest
  echo "Built Behaviors image"
}

buildBehaviors () {
  echo "Building behaviors"
  docker run --rm -v "${workdir}/autobrowser/behaviors/behaviorjs:/dist" -i -t wrbehaviors:latest
  echo "Built behaviors"
}

buildBehaviorPython () {
  echo "Building docker image for python portion"
  docker build . -t autobrowserpy:latest
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

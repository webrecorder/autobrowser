#!/usr/bin/env bash

py () {
  pip install --upgrade -r requirements.txt -r dev-requirements.txt
}

behaviors () {
  docker run -it --rm -v "${PWD}/behaviors:/app/dist" webrecorder/behaviors:latest
}

case "$1" in
    "behaviors"*)
     behaviors
    ;;

    *)
    py
    behaviors
    ;;
esac

#!/usr/bin/env bash

case "$1" in
    "types"*)
     mypy --config-file mypy.ini autobrowser/
    ;;

    "lint"*)
     flake8
    ;;

    *)
     printf "Checking Typing\n"
     mypy --config-file mypy.ini autobrowser/
     printf "\nLinting\n"
     flake8
    ;;
esac

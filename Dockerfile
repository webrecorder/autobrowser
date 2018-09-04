FROM python:3.7

RUN pip install git+https://github.com/iipc/urlcanon.git attrs aioredis async-timeout aiohttp yarl gevent requests bottle jinja2 uvloop numpy redis ujson pyee aiofiles git+https://github.com/webrecorder/simplechrome.git@using-cripy

COPY chrome-remote-interface-py /tmp/chrome-remote-interface-py

RUN cd /tmp/chrome-remote-interface-py && python setup.py install


WORKDIR /tmp


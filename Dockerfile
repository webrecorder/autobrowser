FROM python:3.7

RUN pip install aioredis async-timeout aiohttp yarl gevent requests bottle jinja2 uvloop numpy redis ujson pyee aiofiles

COPY chrome-remote-interface-py /tmp/chrome-remote-interface-py

RUN cd /tmp/chrome-remote-interface-py && python setup.py install


WORKDIR /tmp


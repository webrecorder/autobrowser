FROM python:3.6

RUN pip install gevent requests bottle jinja2 uvloop numpy redis aioredis

COPY chrome-remote-interface-py /tmp/chrome-remote-interface-py

RUN cd /tmp/chrome-remote-interface-py && python setup.py install


WORKDIR /tmp

